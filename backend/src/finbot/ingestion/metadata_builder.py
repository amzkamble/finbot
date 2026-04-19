"""Build RBAC-compliant metadata for each chunk."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from finbot.config.settings import ALL_COLLECTIONS, FOLDER_RBAC_MAP
from finbot.utils.logger import get_logger

logger = get_logger(__name__)

# UUID namespace for deterministic chunk IDs
_FINBOT_NAMESPACE = uuid.UUID("a3f1b2c4-d5e6-7890-abcd-ef1234567890")


@dataclass
class ChunkWithMetadata:
    """A chunk enriched with RBAC and contextual metadata, ready for Qdrant."""

    text: str
    chunk_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


class MetadataBuilder:
    """
    Transform raw Docling chunks into ``ChunkWithMetadata`` objects
    carrying the full RBAC metadata schema.
    """

    def __init__(self, rbac_map: dict[str, list[str]] | None = None) -> None:
        self._rbac_map = rbac_map or FOLDER_RBAC_MAP

    # ── Public API ──────────────────────────────────────────────────────

    def build_batch(self, chunks: list[Any], file_path: Path) -> list[ChunkWithMetadata]:
        """Build metadata for every chunk from the same source file."""
        results: list[ChunkWithMetadata] = []
        for idx, chunk in enumerate(chunks):
            results.append(self.build_metadata(chunk, file_path, idx))
        return results

    def build_metadata(self, chunk: Any, file_path: Path, chunk_index: int) -> ChunkWithMetadata:
        """
        Build the complete metadata payload for a single chunk.

        Metadata schema
        ───────────────
        - source_document : str
        - collection      : str
        - access_roles    : list[str]
        - section_title   : str
        - page_number     : int
        - chunk_type      : str   (text | table | heading | code)
        - parent_chunk_id : str | None
        - chunk_id        : str
        """
        file_path = Path(file_path).resolve()

        source_document = file_path.name
        collection = self._derive_collection(file_path)
        access_roles = self._rbac_map.get(collection, self._rbac_map["general"])
        section_title = self._extract_section_title(chunk)
        page_number = self._extract_page_number(chunk)
        chunk_type = self._classify_chunk_type(chunk)
        chunk_id = self._generate_chunk_id(source_document, collection, chunk_index)
        parent_chunk_id = self._resolve_parent_id(chunk, source_document, collection)

        text = self._extract_text(chunk)

        return ChunkWithMetadata(
            text=text,
            chunk_id=chunk_id,
            metadata={
                "source_document": source_document,
                "collection": collection,
                "access_roles": access_roles,
                "section_title": section_title,
                "page_number": page_number,
                "chunk_type": chunk_type,
                "parent_chunk_id": parent_chunk_id,
                "chunk_id": chunk_id,
            },
        )

    # ── Private helpers ─────────────────────────────────────────────────

    @staticmethod
    def _extract_text(chunk: Any) -> str:
        """Extract the plain text content from a Docling chunk."""
        if hasattr(chunk, "text"):
            return chunk.text
        return str(chunk)

    def _derive_collection(self, file_path: Path) -> str:
        """
        Determine the collection based on the parent folder name.

        ``data/finance/report.pdf`` → ``"finance"``
        """
        parent_name = file_path.parent.name.lower()
        if parent_name in ALL_COLLECTIONS:
            return parent_name
        # Walk up one more level (in case of nested subdirs)
        grandparent = file_path.parent.parent.name.lower()
        if grandparent in ALL_COLLECTIONS:
            return grandparent
        logger.warning(
            "Could not determine collection for '%s', defaulting to 'general'",
            file_path,
        )
        return "general"

    @staticmethod
    def _extract_section_title(chunk: Any) -> str:
        """Extract the most specific heading from the chunk's hierarchy."""
        try:
            headings = chunk.meta.headings
            if headings:
                return headings[-1]  # most specific
        except AttributeError:
            pass
        return "Untitled Section"

    @staticmethod
    def _extract_page_number(chunk: Any) -> int:
        """Extract the page number from chunk provenance metadata."""
        try:
            doc_items = chunk.meta.doc_items
            if doc_items:
                first_item = doc_items[0]
                if hasattr(first_item, "prov") and first_item.prov:
                    return first_item.prov[0].page_no
        except (AttributeError, IndexError):
            pass
        return 1

    @staticmethod
    def _classify_chunk_type(chunk: Any) -> str:
        """
        Determine the chunk_type based on the underlying DocItem labels.

        Returns one of: ``text``, ``table``, ``heading``, ``code``.
        """
        try:
            doc_items = chunk.meta.doc_items
            if doc_items:
                label = str(getattr(doc_items[0], "label", "")).lower()
                if "table" in label:
                    return "table"
                if "head" in label or "title" in label:
                    return "heading"
                if "code" in label:
                    return "code"
        except AttributeError:
            pass
        return "text"

    @staticmethod
    def _generate_chunk_id(source_document: str, collection: str, chunk_index: int) -> str:
        """Generate a deterministic UUID v5 for the chunk."""
        name = f"{source_document}:{collection}:{chunk_index}"
        return str(uuid.uuid5(_FINBOT_NAMESPACE, name))

    @staticmethod
    def _resolve_parent_id(chunk: Any, source_document: str, collection: str) -> str | None:
        """
        Resolve the parent chunk's ID from the heading hierarchy.

        The 'parent' is the chunk representing the next-higher heading level.
        """
        try:
            headings = chunk.meta.headings
            if headings and len(headings) >= 2:
                # Parent heading is the second-to-last in the hierarchy
                parent_heading = headings[-2]
                name = f"{source_document}:{collection}:heading:{parent_heading}"
                return str(uuid.uuid5(_FINBOT_NAMESPACE, name))
        except AttributeError:
            pass
        return None
