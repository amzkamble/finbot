"""Qdrant client wrapper for collection management and vector operations."""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import QdrantClient, models

from finbot.config.settings import get_settings
from finbot.utils.logger import get_logger

logger = get_logger(__name__)


class VectorStore:
    """
    Low-level Qdrant operations: collection management, upsert, search.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        collection_name: str | None = None,
    ) -> None:
        settings = get_settings()
        self._host = host or settings.qdrant_host
        self._port = port or settings.qdrant_port
        self._collection_name = collection_name or settings.qdrant_collection_name
        self._client = QdrantClient(host=self._host, port=self._port)
        logger.info(
            "VectorStore connected to Qdrant at %s:%s, collection='%s'",
            self._host,
            self._port,
            self._collection_name,
        )

    @property
    def client(self) -> QdrantClient:
        return self._client

    @property
    def collection_name(self) -> str:
        return self._collection_name

    # ── Collection Management ───────────────────────────────────────────

    def create_collection_if_not_exists(self, vector_size: int, distance: str = "Cosine") -> bool:
        """
        Create the Qdrant collection if it doesn't already exist.

        Returns ``True`` if the collection was created, ``False`` if it already existed.
        """
        collections = self._client.get_collections().collections
        existing_names = {c.name for c in collections}

        if self._collection_name in existing_names:
            logger.info("Collection '%s' already exists", self._collection_name)
            return False

        dist_map = {
            "Cosine": models.Distance.COSINE,
            "Euclid": models.Distance.EUCLID,
            "Dot": models.Distance.DOT,
        }

        self._client.create_collection(
            collection_name=self._collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=dist_map.get(distance, models.Distance.COSINE),
            ),
        )
        logger.info("Created collection '%s' (size=%d, distance=%s)", self._collection_name, vector_size, distance)
        return True

    def delete_collection(self) -> None:
        """Drop the entire collection."""
        self._client.delete_collection(collection_name=self._collection_name)
        logger.warning("Deleted collection '%s'", self._collection_name)

    def create_payload_indexes(self) -> None:
        """Create keyword indexes on filterable metadata fields."""
        for field in ("collection", "access_roles", "chunk_type", "source_document"):
            self._client.create_payload_index(
                collection_name=self._collection_name,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        logger.info("Payload indexes created on collection '%s'", self._collection_name)

    # ── Write Operations ────────────────────────────────────────────────

    def upsert(self, points: list[models.PointStruct], batch_size: int = 100) -> int:
        """
        Upsert points into the collection in batches.

        Returns the total number of points upserted.
        """
        total = 0
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self._client.upsert(collection_name=self._collection_name, points=batch)
            total += len(batch)
            logger.debug("Upserted batch %d–%d", i, i + len(batch))
        return total

    # ── Read Operations ─────────────────────────────────────────────────

    def search(
        self,
        query_vector: list[float],
        limit: int = 5,
        query_filter: models.Filter | None = None,
    ) -> list[models.ScoredPoint]:
        """
        Perform a filtered vector search and return scored results.
        """
        results = self._client.query_points(
            collection_name=self._collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        return results.points

    def count(self, query_filter: models.Filter | None = None) -> int:
        """Return the number of points matching an optional filter."""
        result = self._client.count(
            collection_name=self._collection_name,
            count_filter=query_filter,
            exact=True,
        )
        return result.count

    def scroll_all(
        self,
        query_filter: models.Filter | None = None,
        limit: int = 100,
    ) -> list[models.Record]:
        """Scroll through all points matching the filter."""
        records, _ = self._client.scroll(
            collection_name=self._collection_name,
            scroll_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        return records
