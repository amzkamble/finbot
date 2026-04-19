"""RAG chain composing retriever → prompt → LLM → output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from finbot.generation.llm_client import LLMClient
from finbot.generation.prompts import RAG_SYSTEM_PROMPT, RAG_USER_PROMPT_TEMPLATE
from finbot.models.responses import SourceInfo
from finbot.retrieval.rbac_retriever import RBACRetriever, RetrievedChunk
from finbot.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RAGResponse:
    """Structured result from the RAG chain."""

    answer: str = ""
    sources: list[SourceInfo] = field(default_factory=list)
    contexts: list[str] = field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0


class RAGChain:
    """
    Full RAG chain that wires together:
    RBAC Retriever → Prompt Builder → LLM → Source Formatter
    """

    def __init__(
        self,
        retriever: RBACRetriever,
        llm: LLMClient,
        top_k: int = 5,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._top_k = top_k

    def run(
        self,
        query: str,
        user_role: str,
        target_collections: list[str] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> RAGResponse:
        """
        Execute the full RAG pipeline.

        Parameters
        ----------
        query : str
            The user's (cleaned) query.
        user_role : str
            The authenticated user's role.
        target_collections : list[str], optional
            Collections to search (from router).
        history : list[dict], optional
            Prior conversation turns for multi-turn context.

        Returns
        -------
        RAGResponse
            Answer + source citations + raw contexts.
        """
        import time

        start = time.time()

        # 1. Retrieve relevant chunks (RBAC-filtered)
        chunks = self._retriever.retrieve(
            query=query,
            user_role=user_role,
            target_collections=target_collections,
            top_k=self._top_k,
        )

        if not chunks:
            return RAGResponse(
                answer="I don't have enough information in the available documents to answer this question. "
                       "This may be because the relevant documents are not accessible with your current role.",
                latency_ms=(time.time() - start) * 1000,
            )

        # 2. Build contexts and prompt
        contexts = [c.text for c in chunks]
        context_block = "\n\n---\n\n".join(
            f"[Context {i+1} — {c.metadata.get('source_document', 'Unknown')}, "
            f"Page {c.metadata.get('page_number', '?')}]:\n{c.text}"
            for i, c in enumerate(chunks)
        )

        user_prompt = RAG_USER_PROMPT_TEMPLATE.format(
            contexts=context_block,
            query=query,
        )

        # 3. Generate LLM response (with conversation history for follow-ups)
        answer = self._llm.generate(
            prompt=user_prompt,
            system_prompt=RAG_SYSTEM_PROMPT,
            history=history,
        )

        # 4. Build source citations
        sources = self._build_sources(chunks)

        # 5. Build raw chunk metadata for output guardrails
        chunk_metadata = [
            {**c.metadata, "text": c.text} for c in chunks
        ]

        elapsed = (time.time() - start) * 1000

        logger.info("RAG chain completed in %.0fms (%d chunks used)", elapsed, len(chunks))

        return RAGResponse(
            answer=answer,
            sources=sources,
            contexts=contexts,
            retrieved_chunks=chunk_metadata,
            latency_ms=elapsed,
        )

    @staticmethod
    def _build_sources(chunks: list[RetrievedChunk]) -> list[SourceInfo]:
        """Deduplicate and format source citations."""
        seen: set[str] = set()
        sources: list[SourceInfo] = []

        for chunk in chunks:
            key = (
                f"{chunk.metadata.get('source_document')}:"
                f"{chunk.metadata.get('page_number')}:"
                f"{chunk.metadata.get('section_title')}"
            )
            if key in seen:
                continue
            seen.add(key)

            sources.append(
                SourceInfo(
                    document=chunk.metadata.get("source_document", "Unknown"),
                    page=chunk.metadata.get("page_number", 1),
                    section=chunk.metadata.get("section_title", "Untitled Section"),
                    collection=chunk.metadata.get("collection", "general"),
                    chunk_type=chunk.metadata.get("chunk_type", "text"),
                )
            )

        return sources
