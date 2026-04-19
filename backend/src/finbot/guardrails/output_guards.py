"""Output guardrails: post-processing checks on LLM responses."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from finbot.auth.rbac import get_accessible_collections
from finbot.config.settings import FOLDER_RBAC_MAP, get_settings
from finbot.guardrails.input_guards import GuardResult, GuardrailPipelineResult
from finbot.utils.logger import get_logger

logger = get_logger(__name__)


# ── Guard 1: Grounding Check ───────────────────────────────────────────────


class GroundingChecker:
    """
    Verify that the LLM response is grounded in retrieved contexts
    and not hallucinated.

    Uses an LLM-as-judge approach when available, or a simple
    token-overlap heuristic as fallback.
    """

    def __init__(self, llm_client: Any = None, threshold: float | None = None) -> None:
        settings = get_settings()
        self._llm = llm_client
        self._threshold = threshold or settings.grounding_threshold

    def check(self, response: str, retrieved_contexts: list[str]) -> GuardResult:
        if not retrieved_contexts:
            return GuardResult(
                passed=True,
                guard_name="grounding_check",
                action="flag",
                message="No contexts were retrieved — response may not be grounded.",
                metadata={"grounding_score": 0.0},
            )

        if self._llm is not None:
            return self._llm_check(response, retrieved_contexts)
        return self._heuristic_check(response, retrieved_contexts)

    def _heuristic_check(self, response: str, contexts: list[str]) -> GuardResult:
        """Token-overlap grounding heuristic."""
        response_tokens = set(response.lower().split())
        context_tokens: set[str] = set()
        for ctx in contexts:
            context_tokens.update(ctx.lower().split())

        if not response_tokens:
            return GuardResult(passed=True, guard_name="grounding_check", action="pass")

        # Remove common stop words for a meaningful overlap check
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for",
                       "of", "and", "or", "but", "not", "with", "this", "that", "it", "as", "by"}
        meaningful_response = response_tokens - stop_words
        meaningful_context = context_tokens - stop_words

        if not meaningful_response:
            return GuardResult(passed=True, guard_name="grounding_check", action="pass")

        overlap = len(meaningful_response & meaningful_context) / len(meaningful_response)

        if overlap < self._threshold:
            return GuardResult(
                passed=True,  # flag, don't block
                guard_name="grounding_check",
                action="flag",
                message=f"Response may contain ungrounded claims (grounding score: {overlap:.2f}).",
                metadata={"grounding_score": round(overlap, 2)},
            )

        return GuardResult(
            passed=True,
            guard_name="grounding_check",
            action="pass",
            metadata={"grounding_score": round(overlap, 2)},
        )

    def _llm_check(self, response: str, contexts: list[str]) -> GuardResult:
        """LLM-based grounding verification."""
        combined_context = "\n\n---\n\n".join(contexts)
        prompt = f"""You are a grounding evaluator. Determine if the response is fully supported by the source passages.

SOURCE PASSAGES:
{combined_context}

RESPONSE TO EVALUATE:
{response}

Respond with ONLY a JSON object:
{{"is_grounded": true/false, "grounding_score": 0.0-1.0, "ungrounded_claims": ["list of ungrounded claims if any"]}}"""

        try:
            llm_response = self._llm.generate(prompt)
            import json

            result = json.loads(llm_response)
            score = result.get("grounding_score", 1.0)
            ungrounded = result.get("ungrounded_claims", [])

            if score < self._threshold:
                return GuardResult(
                    passed=True,
                    guard_name="grounding_check",
                    action="flag",
                    message=f"Response may contain ungrounded claims (grounding score: {score:.2f}).",
                    metadata={"grounding_score": score, "ungrounded_claims": ungrounded},
                )

            return GuardResult(
                passed=True,
                guard_name="grounding_check",
                action="pass",
                metadata={"grounding_score": score},
            )
        except Exception as exc:
            logger.warning("Grounding LLM check failed: %s", exc)
            return GuardResult(
                passed=True,
                guard_name="grounding_check",
                action="pass",
                metadata={"grounding_score": 1.0, "error": str(exc)},
            )


# ── Guard 2: Cross-Role Leakage Check ──────────────────────────────────────


class CrossRoleLeakageChecker:
    """
    Ensure the response doesn't reveal information from collections
    the user cannot access.
    """

    def __init__(self) -> None:
        self._rbac_map = FOLDER_RBAC_MAP

    def check(
        self,
        response: str,
        retrieved_chunks: list[dict[str, Any]],
        user_role: str,
    ) -> GuardResult:
        accessible = set(get_accessible_collections(user_role))

        # Check that every retrieved chunk's collection is accessible
        for chunk in retrieved_chunks:
            chunk_collection = chunk.get("collection", "general")
            chunk_roles = chunk.get("access_roles", [])

            if chunk_collection not in accessible:
                logger.error(
                    "LEAKAGE: Chunk from collection '%s' reached role '%s'",
                    chunk_collection,
                    user_role,
                )
                return GuardResult(
                    passed=False,
                    guard_name="cross_role_leakage",
                    action="block",
                    message="Response contains information from restricted sources. Access denied.",
                    metadata={"leaked_collection": chunk_collection, "user_role": user_role},
                )

            if user_role not in chunk_roles:
                logger.error(
                    "LEAKAGE: Chunk with access_roles=%s reached role '%s'",
                    chunk_roles,
                    user_role,
                )
                return GuardResult(
                    passed=False,
                    guard_name="cross_role_leakage",
                    action="block",
                    message="Response contains information from restricted sources. Access denied.",
                    metadata={"chunk_roles": chunk_roles, "user_role": user_role},
                )

        return GuardResult(passed=True, guard_name="cross_role_leakage", action="pass")


# ── Guard 3: Source Citation Enforcement ────────────────────────────────────


class SourceCitationEnforcer:
    """
    Ensure responses include proper source citations.
    Can auto-append citations if missing.
    """

    _CITATION_PATTERNS = [
        r"\[Source:.*?\]",
        r"\[.*?\.\w{2,4}.*?\]",  # [filename.pdf]
        r"\*\*Sources?\*\*\s*:",
        r"📄\s+\w+",
    ]

    def __init__(self, min_citations: int | None = None) -> None:
        settings = get_settings()
        self._min_citations = min_citations or settings.min_citations

    def check(
        self,
        response: str,
        retrieved_chunks: list[dict[str, Any]],
    ) -> GuardResult:
        # Check for "I don't know" or clarification responses (exempt)
        no_answer_patterns = [
            r"i don'?t (know|have)",
            r"i('m| am) not (sure|able)",
            r"could you (clarify|rephrase)",
            r"no (relevant )?(information|data|documents?) (found|available)",
        ]
        for pat in no_answer_patterns:
            if re.search(pat, response.lower()):
                return GuardResult(
                    passed=True,
                    guard_name="source_citation",
                    action="pass",
                    metadata={"reason": "response_is_clarification"},
                )

        # Count citations in the response
        citation_count = 0
        for pattern in self._CITATION_PATTERNS:
            citation_count += len(re.findall(pattern, response, re.IGNORECASE))

        if citation_count >= self._min_citations:
            return GuardResult(
                passed=True,
                guard_name="source_citation",
                action="pass",
                metadata={"citation_count": citation_count},
            )

        # Auto-append citations
        if retrieved_chunks:
            citations_block = self._build_citations(retrieved_chunks)
            modified = response.rstrip() + "\n\n" + citations_block

            return GuardResult(
                passed=True,
                guard_name="source_citation",
                action="modify",
                message="Citations were automatically added to the response.",
                modified_content=modified,
                metadata={"citation_count": len(retrieved_chunks), "auto_added": True},
            )

        return GuardResult(
            passed=True,
            guard_name="source_citation",
            action="flag",
            message="Response lacks source citations and no sources are available.",
            metadata={"citation_count": 0},
        )

    @staticmethod
    def _build_citations(chunks: list[dict[str, Any]]) -> str:
        """Format retrieved chunks into a citation block."""
        lines = ["**Sources:**"]
        seen: set[str] = set()
        for chunk in chunks:
            doc = chunk.get("source_document", "Unknown")
            page = chunk.get("page_number", "")
            section = chunk.get("section_title", "")
            key = f"{doc}:{page}:{section}"
            if key in seen:
                continue
            seen.add(key)
            parts = [f"📄 {doc}"]
            if page:
                parts.append(f"Page {page}")
            if section and section != "Untitled Section":
                parts.append(f'Section: "{section}"')
            lines.append(f"- {' — '.join(parts)}")
        return "\n".join(lines)


# ── Output Guardrail Pipeline ──────────────────────────────────────────────


class OutputGuardrailPipeline:
    """
    Execute all output guards in order:
    Cross-Role Leakage → Grounding Check → Source Citation

    Blocks on leakage, flags on grounding, modifies for citations.
    """

    def __init__(
        self,
        leakage_checker: CrossRoleLeakageChecker | None = None,
        grounding_checker: GroundingChecker | None = None,
        citation_enforcer: SourceCitationEnforcer | None = None,
    ) -> None:
        self._leakage = leakage_checker or CrossRoleLeakageChecker()
        self._grounding = grounding_checker or GroundingChecker()
        self._citation = citation_enforcer or SourceCitationEnforcer()

    def run(
        self,
        response: str,
        retrieved_chunks: list[dict[str, Any]],
        user_role: str,
    ) -> GuardrailPipelineResult:
        """Run the full output guardrail pipeline."""
        results: list[GuardResult] = []
        current_content = response
        contexts = [c.get("text", "") for c in retrieved_chunks]

        # 1. Cross-role leakage (security-critical, fast)
        leakage_result = self._leakage.check(current_content, retrieved_chunks, user_role)
        results.append(leakage_result)
        if leakage_result.action == "block":
            return GuardrailPipelineResult(
                passed=False,
                results=results,
                final_content="I'm unable to provide that information based on your current access level.",
                blocked_by="cross_role_leakage",
            )

        # 2. Grounding check (quality)
        grounding_result = self._grounding.check(current_content, contexts)
        results.append(grounding_result)

        # 3. Source citation enforcement (can modify)
        citation_result = self._citation.check(current_content, retrieved_chunks)
        results.append(citation_result)
        if citation_result.action == "modify" and citation_result.modified_content:
            current_content = citation_result.modified_content

        return GuardrailPipelineResult(
            passed=True,
            results=results,
            final_content=current_content,
        )
