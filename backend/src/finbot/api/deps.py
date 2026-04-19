"""FastAPI dependency injection for the FinBot API."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException

from finbot.auth.jwt_handler import decode_token
from finbot.auth.models import User, get_user_by_id
from finbot.config.settings import Settings, get_settings
from finbot.utils.logger import get_logger

logger = get_logger(__name__)

# ── Singletons (initialised lazily) ────────────────────────────────────────

_components: dict[str, Any] = {}


def _get_component(name: str) -> Any:
    """Return a lazily-initialised singleton component."""
    return _components.get(name)


def init_components() -> None:
    """Initialise all heavyweight components (called on first request)."""
    if _components:
        return  # already initialised

    settings = get_settings()

    from finbot.chat.memory import ChatMemory
    from finbot.generation.llm_client import LLMClient
    from finbot.guardrails.input_guards import InputGuardrailPipeline
    from finbot.guardrails.output_guards import OutputGuardrailPipeline
    from finbot.retrieval.embedder import Embedder
    from finbot.retrieval.rbac_retriever import RBACRetriever
    from finbot.retrieval.vector_store import VectorStore

    chat_memory = ChatMemory()
    embedder = Embedder()
    vector_store = VectorStore()
    retriever = RBACRetriever(embedder, vector_store)
    llm = LLMClient()

    from finbot.generation.chain import RAGChain

    rag_chain = RAGChain(retriever=retriever, llm=llm)

    # Initialise guardrails (LLM-backed guards use the same LLM client)
    from finbot.guardrails.input_guards import (
        OffTopicGuard,
        PIIScrubber,
        PromptInjectionGuard,
        RateLimiter,
    )
    from finbot.guardrails.output_guards import (
        CrossRoleLeakageChecker,
        GroundingChecker,
        SourceCitationEnforcer,
    )

    input_pipeline = InputGuardrailPipeline(
        rate_limiter=RateLimiter(),
        injection_guard=PromptInjectionGuard(llm_client=llm, enable_llm_check=settings.enable_llm_injection_check),
        pii_scrubber=PIIScrubber(),
        off_topic_guard=OffTopicGuard(llm_client=llm if settings.enable_off_topic_check else None),
    )
    output_pipeline = OutputGuardrailPipeline(
        leakage_checker=CrossRoleLeakageChecker(),
        grounding_checker=GroundingChecker(llm_client=llm),
        citation_enforcer=SourceCitationEnforcer(),
    )

    # Try to initialise the semantic router (may fail if no API key)
    try:
        from finbot.routing.router import QueryRouter

        query_router = QueryRouter()
        _components["query_router"] = query_router
    except Exception as exc:
        logger.warning("Semantic router init failed (will use fallback): %s", exc)

    _components["chat_memory"] = chat_memory
    _components["embedder"] = embedder
    _components["vector_store"] = vector_store
    _components["retriever"] = retriever
    _components["llm"] = llm
    _components["rag_chain"] = rag_chain
    _components["input_guardrails"] = input_pipeline
    _components["output_guardrails"] = output_pipeline

    logger.info("All components initialised successfully")


# ── Dependencies ────────────────────────────────────────────────────────────


async def get_current_user(authorization: str = Header(default="")) -> User:
    """Extract and validate the current user from the JWT token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token)

    user = get_user_by_id(payload["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def require_executive(user: User = Depends(get_current_user)) -> User:
    """Require the ``executive`` role for admin endpoints."""
    if user.role != "executive":
        raise HTTPException(status_code=403, detail="Executive role required")
    return user


def get_rag_chain() -> Any:
    init_components()
    return _get_component("rag_chain")


def get_query_router() -> Any:
    init_components()
    return _get_component("query_router")


def get_input_guardrails() -> Any:
    init_components()
    return _get_component("input_guardrails")


def get_output_guardrails() -> Any:
    init_components()
    return _get_component("output_guardrails")


def get_vector_store() -> Any:
    init_components()
    return _get_component("vector_store")


def get_chat_memory() -> Any:
    init_components()
    return _get_component("chat_memory")
