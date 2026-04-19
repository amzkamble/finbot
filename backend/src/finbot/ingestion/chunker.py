"""Hierarchical chunker using Docling's built-in chunking strategy."""

from __future__ import annotations

from typing import Any

from docling_core.transforms.chunker import HierarchicalChunker

from finbot.utils.logger import get_logger

logger = get_logger(__name__)


class HierarchicalDocumentChunker:
    """
    Apply Docling's ``HierarchicalChunker`` to a ``DoclingDocument``
    to produce chunks that preserve heading hierarchy and structural elements.
    """

    def __init__(self, merge_peers: bool = True) -> None:
        """
        Parameters
        ----------
        merge_peers : bool
            Whether to merge sibling chunks under the same heading into
            a single chunk.  ``True`` gives fewer, richer chunks.
        """
        self._chunker = HierarchicalChunker(merge_peers=merge_peers)
        logger.info("HierarchicalDocumentChunker initialised (merge_peers=%s)", merge_peers)

    def chunk(self, document: Any) -> list[Any]:
        """
        Chunk a ``DoclingDocument`` using the hierarchical strategy.

        Parameters
        ----------
        document : DoclingDocument
            The parsed document from ``DocumentParser.parse()``.

        Returns
        -------
        list
            List of Docling chunk objects.  Each chunk contains:

            - ``text`` — the chunk's content
            - ``meta.headings`` — ancestor heading list (the hierarchy)
            - ``meta.origin`` — reference to the source document
            - ``meta.doc_items`` — underlying ``DocItem`` references with
              provenance (page numbers, bounding boxes, etc.)
        """
        chunks = list(self._chunker.chunk(document))
        logger.info("Produced %d chunks from document", len(chunks))
        return chunks
