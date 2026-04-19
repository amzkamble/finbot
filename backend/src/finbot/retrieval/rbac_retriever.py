"""RBAC-filtered retriever that combines routing, embedding, and Qdrant search."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from qdrant_client import models

from finbot.auth.rbac import check_access, get_accessible_collections
from finbot.retrieval.embedder import Embedder
from finbot.retrieval.vector_store import VectorStore
from finbot.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    """A single chunk returned from RBAC-filtered retrieval."""

    text: str
    score: float
    chunk_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


class RBACRetriever:
    """
    Orchestrates RBAC-filtered vector retrieval.

    1. Receives target collections from the Semantic Router.
    2. Embeds the query.
    3. Searches Qdrant with metadata filter on ``access_roles``.
    4. Returns ranked chunks with full metadata.
    """

    def __init__(self, embedder: Embedder, vector_store: VectorStore, top_k: int = 5) -> None:
        self._embedder = embedder
        self._store = vector_store
        self._top_k = top_k

    def retrieve(
        self,
        query: str,
        user_role: str,
        target_collections: list[str] | None = None,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """
        Retrieve the most relevant chunks the user is allowed to see.

        Parameters
        ----------
        query : str
            The user's (possibly cleaned) query.
        user_role : str
            The authenticated user's role.
        target_collections : list[str], optional
            Collections to search (from the router).  Falls back to all
            collections accessible by the role.
        top_k : int, optional
            Override for the default number of results.

        Returns
        -------
        list[RetrievedChunk]
            Ranked results with text, score, and metadata.
        """
        k = top_k or self._top_k

        # Determine which collections to search
        if target_collections:
            # Filter to only collections the user can actually access
            collections = [c for c in target_collections if check_access(user_role, c)]
            if not collections:
                collections = get_accessible_collections(user_role)
        else:
            collections = get_accessible_collections(user_role)

        logger.info(
            "Retrieving top-%d for role='%s', collections=%s",
            k,
            user_role,
            collections,
        )

        # Build Qdrant filter: collection IN target_collections AND role IN access_roles
        qdrant_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="collection",
                    match=models.MatchAny(any=collections),
                ),
                models.FieldCondition(
                    key="access_roles",
                    match=models.MatchAny(any=[user_role]),
                ),
            ]
        )

        # Embed and search
        query_vector = self._embedder.embed(query)
        scored_points = self._store.search(
            query_vector=query_vector,
            limit=k,
            query_filter=qdrant_filter,
        )

        # Convert to RetrievedChunk
        chunks: list[RetrievedChunk] = []
        for point in scored_points:
            payload = point.payload or {}
            chunks.append(
                RetrievedChunk(
                    text=payload.get("text", ""),
                    score=point.score,
                    chunk_id=str(point.id),
                    metadata={
                        "source_document": payload.get("source_document", ""),
                        "collection": payload.get("collection", ""),
                        "access_roles": payload.get("access_roles", []),
                        "section_title": payload.get("section_title", ""),
                        "page_number": payload.get("page_number", 1),
                        "chunk_type": payload.get("chunk_type", "text"),
                        "parent_chunk_id": payload.get("parent_chunk_id"),
                    },
                )
            )

        logger.info("Retrieved %d chunks for query", len(chunks))
        return chunks
