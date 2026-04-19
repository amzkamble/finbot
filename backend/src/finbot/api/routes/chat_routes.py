"""Chat endpoint — the core RAG pipeline."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Query

from finbot.api.deps import (
    get_chat_memory,
    get_current_user,
    get_input_guardrails,
    get_output_guardrails,
    get_query_router,
    get_rag_chain,
)
from finbot.auth.models import User
from finbot.auth.rbac import get_accessible_collections
from finbot.models.requests import ChatRequest
from finbot.models.responses import (
    ChatResponse,
    GuardrailInfo,
    InputGuardInfo,
    OutputGuardInfo,
    RouteInfo,
)
from finbot.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
) -> ChatResponse:
    """
    Process a user query through the full RAG + RBAC pipeline.

    Pipeline: Auth → Input Guardrails → Routing → Retrieval → Generation → Output Guardrails
    """
    start = time.time()

    # ── 1. Input Guardrails ─────────────────────────────────────────────
    input_pipeline = get_input_guardrails()
    if input_pipeline:
        input_result = input_pipeline.run(body.message, user.id)

        if not input_result.passed:
            # Build guardrail info for the blocked response
            input_info = InputGuardInfo(
                injection_detected=input_result.blocked_by == "prompt_injection_detection",
            )
            return ChatResponse(
                answer="",
                blocked=True,
                blocked_reason=input_result.blocked_by,
                guardrails=GuardrailInfo(input=input_info),
                metadata={"latency_ms": round((time.time() - start) * 1000)},
            )

        cleaned_query = input_result.final_content
        pii_scrubbed = any(r.action == "modify" for r in input_result.results)
    else:
        cleaned_query = body.message
        pii_scrubbed = False

    # ── 2. Semantic Routing ─────────────────────────────────────────────
    query_router = get_query_router()
    if query_router:
        route_result = query_router.classify(cleaned_query, user.role)
        route_info = RouteInfo(
            name=route_result.route_name,
            confidence=route_result.confidence,
            was_rbac_filtered=route_result.was_rbac_filtered,
            original_route=route_result.original_route,
            collections_searched=route_result.target_collections,
        )
        target_collections = route_result.target_collections
    else:
        # Fallback: search all accessible collections
        accessible = get_accessible_collections(user.role)
        route_info = RouteInfo(
            name="fallback",
            confidence=0.0,
            collections_searched=accessible,
        )
        target_collections = accessible

    # ── 3. RAG Chain (Retrieve + Generate) ──────────────────────────────
    rag_chain = get_rag_chain()
    chat_memory = get_chat_memory()

    # Load conversation history for this session
    history = chat_memory.get_history(body.session_id) if body.session_id else []

    rag_response = rag_chain.run(
        query=cleaned_query,
        user_role=user.role,
        target_collections=target_collections,
        history=history,
    )
    
    final_answer = rag_response.answer

    # ── Polite RBAC Denial Logic ────────────────────────────────────────
    # If the router caught a restricted route, let the user know politely.
    if route_info.was_rbac_filtered and route_info.original_route:
        dept = route_info.original_route.replace("_route", "").replace("_", " ").title()
        role_label = user.role.replace("_", " ").title()
        denial_msg = (
            f"> ℹ️ **Note:** I detected a request for **{dept}** information. "
            f"As a **{role_label}**, you don't have access to those documents, "
            f"so I've searched the general and department-specific files available to you.\n\n"
        )
        final_answer = denial_msg + final_answer

    # Save the turn to memory
    if body.session_id:
        chat_memory.add_user_message(body.session_id, body.message)
        chat_memory.add_assistant_message(body.session_id, rag_response.answer)

    # ── 4. Output Guardrails ────────────────────────────────────────────
    output_pipeline = get_output_guardrails()
    grounding_score = 1.0
    grounding_warning = False
    citations_auto_added = False
    leakage_detected = False

    if output_pipeline:
        output_result = output_pipeline.run(
            response=rag_response.answer,
            retrieved_chunks=rag_response.retrieved_chunks,
            user_role=user.role,
        )

        if not output_result.passed:
            return ChatResponse(
                answer="I'm unable to provide that information based on your current access level.",
                blocked=True,
                blocked_reason=output_result.blocked_by,
                route=route_info,
                metadata={"latency_ms": round((time.time() - start) * 1000)},
            )

        final_answer = output_result.final_content

        # Extract guardrail details
        for r in output_result.results:
            if r.guard_name == "grounding_check":
                grounding_score = r.metadata.get("grounding_score", 1.0)
                grounding_warning = r.action == "flag"
            elif r.guard_name == "source_citation":
                citations_auto_added = r.metadata.get("auto_added", False)
            elif r.guard_name == "cross_role_leakage":
                leakage_detected = r.action == "block"
    else:
        final_answer = rag_response.answer

    elapsed = (time.time() - start) * 1000

    # ── 5. Audit Log ────────────────────────────────────────────────────
    chat_memory.log_query(
        session_id=body.session_id,
        user_id=user.id,
        user_role=user.role,
        query=body.message,
        route_name=route_info.name,
        route_confidence=route_info.confidence,
        was_rbac_filtered=route_info.was_rbac_filtered,
        original_route=route_info.original_route,
        collections_searched=target_collections,
        chunks_retrieved=len(rag_response.sources),
        latency_ms=elapsed,
    )

    return ChatResponse(
        answer=final_answer,
        sources=rag_response.sources,
        route=route_info,
        guardrails=GuardrailInfo(
            input=InputGuardInfo(
                pii_scrubbed=pii_scrubbed,
            ),
            output=OutputGuardInfo(
                grounding_score=round(grounding_score, 2),
                grounding_warning=grounding_warning,
                leakage_detected=leakage_detected,
                citations_auto_added=citations_auto_added,
            ),
        ),
        metadata={
            "latency_ms": round(elapsed),
            "collections_searched": target_collections,
            "chunks_retrieved": len(rag_response.sources),
            "role": user.role,
        },
    )


@router.get("/history")
async def get_chat_history(
    session_id: str = Query(..., min_length=1),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Return the conversation history for a session from SQLite."""
    chat_memory = get_chat_memory()
    return chat_memory.get_history(session_id)
