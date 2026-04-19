"""Document parser using IBM Docling for multi-format conversion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from finbot.config.settings import SUPPORTED_EXTENSIONS
from finbot.utils.exceptions import ConversionError, UnsupportedFormatError
from finbot.utils.logger import get_logger

logger = get_logger(__name__)

# Map file extensions to Docling InputFormat
_EXT_TO_FORMAT: dict[str, InputFormat] = {
    ".pdf": InputFormat.PDF,
    ".docx": InputFormat.DOCX,
    ".md": InputFormat.MD,
    ".csv": InputFormat.CSV,
    ".pptx": InputFormat.PPTX,
}


class DocumentParser:
    """
    Wraps IBM Docling's ``DocumentConverter`` to convert documents from
    multiple formats into a unified ``DoclingDocument`` representation.
    """

    def __init__(self) -> None:
        # Configure PDF pipeline with table-structure recognition
        pdf_pipeline_options = PdfPipelineOptions()
        pdf_pipeline_options.do_table_structure = True

        self._converter = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.DOCX,
                InputFormat.MD,
                InputFormat.CSV,
                InputFormat.PPTX,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_pipeline_options),
            },
        )
        logger.info("DocumentParser initialised (formats: %s)", list(_EXT_TO_FORMAT.keys()))

    # ── Public API ──────────────────────────────────────────────────────

    def parse(self, file_path: Path) -> Any:
        """
        Convert a single document to a ``DoclingDocument``.

        Parameters
        ----------
        file_path : Path
            Absolute or relative path to the source document.

        Returns
        -------
        DoclingDocument
            The structured Docling representation.

        Raises
        ------
        FileNotFoundError
            If *file_path* does not exist.
        UnsupportedFormatError
            If the extension is not supported.
        ConversionError
            If Docling fails to convert the document.
        """
        file_path = Path(file_path).resolve()

        if not file_path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFormatError(file_path.suffix)

        logger.info("Parsing document: %s", file_path.name)
        try:
            result = self._converter.convert(str(file_path))
            return result.document
        except Exception as exc:
            logger.error("Conversion failed for '%s': %s", file_path.name, exc)
            raise ConversionError(str(file_path), str(exc)) from exc

    def parse_directory(self, dir_path: Path) -> list[tuple[Path, Any]]:
        """
        Parse every supported document under *dir_path* (recursive).

        Returns a list of ``(file_path, DoclingDocument)`` tuples.
        Errors on individual files are logged and skipped.
        """
        dir_path = Path(dir_path).resolve()
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {dir_path}")

        documents: list[tuple[Path, Any]] = []
        supported_files = [
            f for f in sorted(dir_path.rglob("*")) if f.suffix.lower() in SUPPORTED_EXTENSIONS
        ]

        logger.info("Found %d supported files in '%s'", len(supported_files), dir_path)

        for file_path in supported_files:
            try:
                doc = self.parse(file_path)
                documents.append((file_path, doc))
            except (UnsupportedFormatError, ConversionError) as exc:
                logger.warning("Skipping '%s': %s", file_path.name, exc.message)

        return documents
