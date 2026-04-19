"""Embedding model wrapper using sentence-transformers (local, free)."""

from __future__ import annotations

from typing import Any

from sentence_transformers import SentenceTransformer

from finbot.config.settings import get_settings
from finbot.utils.logger import get_logger

logger = get_logger(__name__)


class Embedder:
    """
    Local embedding using sentence-transformers.

    Default model: ``all-MiniLM-L6-v2`` (384 dimensions, fast, free).
    No API key required.
    """

    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        self._model_name = model or settings.embedding_model
        self._model = SentenceTransformer(self._model_name)
        self._dimension = self._model.get_sentence_embedding_dimension()
        logger.info(
            "Embedder initialised with model='%s' (dim=%d)",
            self._model_name,
            self._dimension,
        )

    @property
    def dimension(self) -> int:
        """Return the vector dimension for the active model."""
        return self._dimension

    # ── Public API ──────────────────────────────────────────────────────

    def embed(self, text: str) -> list[float]:
        """Embed a single piece of text and return the vector."""
        vector = self._model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        """
        Embed a list of texts in batches.

        Parameters
        ----------
        texts : list[str]
            The texts to embed.
        batch_size : int
            Batch size for encoding.

        Returns
        -------
        list[list[float]]
            One vector per input text, in the same order.
        """
        logger.debug("Embedding %d texts with batch_size=%d", len(texts), batch_size)
        vectors = self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 100,
        )
        return vectors.tolist()
