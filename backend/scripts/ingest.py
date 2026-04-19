"""CLI tool for bulk document ingestion into Qdrant."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure the src directory is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

print("Initializing FinBot ingestion... Loading document parsing models (this can take several minutes on the first run).")

from finbot.config.settings import ALL_COLLECTIONS, get_settings
from finbot.ingestion.chunker import HierarchicalDocumentChunker
from finbot.ingestion.metadata_builder import MetadataBuilder
from finbot.ingestion.parser import DocumentParser
from finbot.ingestion.uploader import QdrantUploader
from finbot.retrieval.embedder import Embedder
from finbot.retrieval.vector_store import VectorStore
from finbot.utils.logger import get_logger

logger = get_logger(__name__)
print("All modules loaded successfully.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FinBot - Bulk Document Ingestion CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Root data directory (default: from settings)",
    )
    parser.add_argument(
        "--collections",
        nargs="*",
        default=None,
        help="Collections to ingest (default: all). Example: --collections finance engineering",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Embedding batch size (default: 64)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate the Qdrant collection before ingesting",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and chunk only -- do not upload to Qdrant",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()

    data_dir = Path(args.data_dir).resolve() if args.data_dir else settings.data_path
    target_collections = args.collections or ALL_COLLECTIONS

    print("=" * 60)
    print("  FinBot Document Ingestion")
    print("=" * 60)
    print(f"  Data directory  : {data_dir}")
    print(f"  Collections     : {target_collections}")
    print(f"  Batch size      : {args.batch_size}")
    print(f"  Recreate        : {args.recreate}")
    print(f"  Dry run         : {args.dry_run}")
    print("=" * 60)

    # Initialise components
    parser = DocumentParser()
    chunker = HierarchicalDocumentChunker()
    metadata_builder = MetadataBuilder()

    if not args.dry_run:
        embedder = Embedder()
        vector_store = VectorStore()

        if args.recreate:
            print("\n[!] Recreating Qdrant collection ...")
            try:
                vector_store.delete_collection()
            except Exception:
                pass  # Collection may not exist yet
            vector_store.create_collection_if_not_exists(vector_size=embedder.dimension)

        uploader = QdrantUploader(embedder, vector_store, batch_size=args.batch_size)

    # Track statistics
    stats = {
        "documents_processed": 0,
        "total_chunks": 0,
        "by_collection": {},
        "by_type": {"text": 0, "table": 0, "heading": 0, "code": 0},
        "errors": [],
    }

    start_time = time.time()

    for collection in target_collections:
        collection_dir = data_dir / collection
        if not collection_dir.is_dir():
            print(f"\n[SKIP] Skipping '{collection}' -- directory not found: {collection_dir}")
            continue

        print(f"\n[DIR] Processing collection: {collection}")

        # Parse all documents in the collection folder
        try:
            doc_pairs = parser.parse_directory(collection_dir)
        except Exception as exc:
            msg = f"Failed to parse directory '{collection}': {exc}"
            logger.error(msg)
            stats["errors"].append(msg)
            continue

        collection_chunks = 0

        for file_path, document in doc_pairs:
            print(f"   [FILE] {file_path.name} ... ", end="", flush=True)

            # Chunk the document
            try:
                chunks = chunker.chunk(document)
            except Exception as exc:
                msg = f"Chunking failed for '{file_path.name}': {exc}"
                logger.error(msg)
                stats["errors"].append(msg)
                print("[FAIL] chunking failed")
                continue

            # Build metadata
            enriched_chunks = metadata_builder.build_batch(chunks, file_path)

            # Count chunk types
            for ec in enriched_chunks:
                ct = ec.metadata.get("chunk_type", "text")
                stats["by_type"][ct] = stats["by_type"].get(ct, 0) + 1

            collection_chunks += len(enriched_chunks)
            stats["documents_processed"] += 1

            if not args.dry_run:
                result = uploader.upload(enriched_chunks)
                if result.failed > 0:
                    print(f"[WARN] {len(enriched_chunks)} chunks ({result.failed} failed)")
                    stats["errors"].extend(result.errors or [])
                else:
                    print(f"[OK] {len(enriched_chunks)} chunks")
            else:
                print(f"[DRY RUN] {len(enriched_chunks)} chunks")

        stats["by_collection"][collection] = collection_chunks
        stats["total_chunks"] += collection_chunks

    elapsed = time.time() - start_time

    # Print summary
    print("\n" + "=" * 60)
    print("  Ingestion Summary")
    print("=" * 60)
    print(f"  Documents processed : {stats['documents_processed']}")
    print(f"  Total chunks        : {stats['total_chunks']}")
    print(f"  Time elapsed        : {elapsed:.1f}s")
    print()
    print("  Chunks by collection:")
    for col, count in stats["by_collection"].items():
        print(f"    {col:20s} : {count}")
    print()
    print("  Chunks by type:")
    for ct, count in stats["by_type"].items():
        print(f"    {ct:20s} : {count}")

    if stats["errors"]:
        print(f"\n  [!] {len(stats['errors'])} error(s) encountered:")
        for err in stats["errors"]:
            print(f"    - {err}")

    print("=" * 60)


if __name__ == "__main__":
    main()
