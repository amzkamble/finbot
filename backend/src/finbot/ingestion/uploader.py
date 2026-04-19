"""Embed enriched chunks and upload them to Qdrant."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from qdrant_client import models

from finbot.ingestion.metadata_builder import ChunkWithMetadata
from finbot.retrieval.embedder import Embedder
from finbot.retrieval.vector_store import VectorStore
from finbot.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class UploadResult:
    """Summary of an upload operation."""

    total: int = 0
    successful: int = 0
    failed: int = 0
    errors: list[str] | None = None


class QdrantUploader:
    """
    Embed ``ChunkWithMetadata`` objects and upsert them to Qdrant
    with full metadata payloads for RBAC-filtered retrieval.
    """

    def __init__(
        self,
        embedder: Embedder,
        vector_store: VectorStore,
        batch_size: int = 64,
    ) -> None:
        self._embedder = embedder
        self._store = vector_store
        self._batch_size = batch_size

    def upload(self, chunks: list[ChunkWithMetadata]) -> UploadResult:
        """
        Embed and upsert a list of enriched chunks to Qdrant.

        Parameters
        ----------
        chunks : list[ChunkWithMetadata]
            Chunks with text and metadata from ``MetadataBuilder``.

        Returns
        -------
        UploadResult
            Summary with counts of successful / failed uploads.
        """
        if not chunks:
            logger.warning("No chunks to upload")
            return UploadResult()

        result = UploadResult(total=len(chunks), errors=[])

        # 1. Ensure collection exists
        self._store.create_collection_if_not_exists(vector_size=self._embedder.dimension)

        # 2. Batch embed
        texts = [c.text for c in chunks]
        logger.info("Embedding %d chunks …", len(texts))
        try:
            vectors = self._embedder.embed_batch(texts, batch_size=self._batch_size)
        except Exception as exc:
            logger.error("Embedding failed: %s", exc)
            result.failed = result.total
            result.errors.append(f"Embedding failed: {exc}")
            return result

        # 3. Build Qdrant points
        points: list[models.PointStruct] = []
        for chunk, vector in zip(chunks, vectors):
            point_id = chunk.chunk_id
            # Qdrant requires UUID or int IDs
            try:
                point_uuid = uuid.UUID(point_id)
            except ValueError:
                point_uuid = uuid.uuid5(uuid.NAMESPACE_URL, point_id)

            payload = {**chunk.metadata, "text": chunk.text}
            points.append(
                models.PointStruct(
                    id=str(point_uuid),
                    vector=vector,
                    payload=payload,
                )
            )

        # 4. Upsert in batches
        try:
            upserted = self._store.upsert(points, batch_size=100)
            result.successful = upserted
            logger.info("Successfully upserted %d points", upserted)
        except Exception as exc:
            logger.error("Upsert failed: %s", exc)
            result.failed = result.total
            result.errors.append(f"Upsert failed: {exc}")
            return result

        # 5. Create payload indexes for efficient filtering
        try:
            self._store.create_payload_indexes()
        except Exception as exc:
            logger.warning("Payload index creation failed (non-fatal): %s", exc)

        return result
