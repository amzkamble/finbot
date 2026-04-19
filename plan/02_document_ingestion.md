# Step 2: Document Ingestion Pipeline (Task 1)

## Objective
Build a robust document ingestion pipeline using **IBM Docling** for multi-format parsing with **Hierarchical Chunking** that produces RBAC-tagged chunks ready for vector storage in Qdrant.

---

## Overview

```
                 ┌──────────────┐
                 │  data/       │
                 │  ├── general/│
  Source Docs    │  ├── finance/│
  (PDF,MD,DOCX,  │  ├── engineering/
   CSV,PPTX)    │  ├── marketing/
                 │  └── hr/    │
                 └──────┬───────┘
                        │
                        ▼
              ┌──────────────────┐
              │  DocumentParser  │  parser.py
              │  (Docling)       │
              └────────┬─────────┘
                       │ DoclingDocument
                       ▼
              ┌──────────────────┐
              │ HierarchicalDocumentChunker │  chunker.py
              │ (Docling Chunker)│
              └────────┬─────────┘
                       │ List[Chunk]
                       ▼
              ┌──────────────────┐
              │ MetadataBuilder  │  metadata_builder.py
              │ (RBAC + context) │
              └────────┬─────────┘
                       │ List[ChunkWithMetadata]
                       ▼
              ┌──────────────────┐
              │ QdrantUploader   │  uploader.py
              │ (Embed + Upsert) │
              └──────────────────┘
                       │
                       ▼
              ┌──────────────────┐
              │ Qdrant Vector DB │
              └──────────────────┘
```

---

## Files to Implement

### 1. `backend/src/finbot/ingestion/parser.py`

#### Purpose
Wrap IBM Docling's `DocumentConverter` to convert documents from multiple formats (PDF, DOCX, MD, CSV, PPTX) into a unified `DoclingDocument` representation.

#### Class: `DocumentParser`

##### Constructor
- Accept optional configuration for Docling format options (e.g., `PdfFormatOption`, `WordFormatOption`)
- Set up `InputFormat` → format option mapping for all supported formats
- Configure OCR if needed (for scanned PDFs)
- Instantiate `DocumentConverter` with the pipeline options

##### Method: `parse(file_path: Path) → DoclingDocument`
- Validate that the file exists and has a supported extension
- Call `DocumentConverter.convert(file_path)` to get a `ConversionResult`
- Extract and return the `DoclingDocument` from the result
- Handle conversion errors gracefully (log and raise custom exception)

##### Method: `parse_directory(dir_path: Path) → list[tuple[Path, DoclingDocument]]`
- Recursively scan for supported file types
- Call `parse()` on each file
- Return list of (file_path, document) tuples
- Support parallel processing via `convert_all()` for batch efficiency

##### Supported Formats & Docling Mapping
| Extension | Docling InputFormat | Format Option Class |
|-----------|-------------------|---------------------|
| `.pdf` | `InputFormat.PDF` | `PdfFormatOption` |
| `.docx` | `InputFormat.DOCX` | `WordFormatOption` |
| `.md` | `InputFormat.MD` | `MarkdownFormatOption` (default) |
| `.csv` | `InputFormat.CSV` | `CsvFormatOption` (default) |
| `.pptx` | `InputFormat.PPTX` | `PowerpointFormatOption` |

##### Error Handling
- `FileNotFoundError` — document path doesn't exist
- `UnsupportedFormatError` — file extension not in supported list
- `ConversionError` — Docling failed to convert the document

---

### 2. `backend/src/finbot/ingestion/chunker.py`

#### Purpose
Apply Docling's `HierarchicalChunker` to a `DoclingDocument` to produce chunks that preserve the document's heading hierarchy and structural elements.

#### Class: `HierarchicalDocumentChunker`

##### Constructor
- Configure `HierarchicalChunker` from `docling_core.transforms.chunker`
- Set parameters:
  - `merge_peers`: Whether to merge sibling chunks under the same heading (recommend: `True`)
  - Optionally set max chunk size if supported

##### Method: `chunk(document: DoclingDocument) → list[DoclingChunk]`
- Apply `HierarchicalChunker.chunk(document)` 
- Returns a list of chunks, each containing:
  - `text`: the chunk's content
  - `meta`: chunk-level metadata from Docling (headings, page numbers, etc.)
  - `meta.headings`: list of parent headings (the hierarchy)
  - `meta.origin`: reference to source document
  - Structural type info (text, table, heading, code)

##### Key Behavior of Hierarchical Chunking
- **Heading-based splitting:** Chunks are split at heading boundaries
- **Parent-child relationships:** Each chunk knows its parent heading context
- **Table preservation:** Tables are kept as individual chunks, not split mid-row
- **Code block preservation:** Code blocks remain intact
- **Heading inheritance:** Each chunk carries all ancestor headings in `meta.headings`

##### How to Determine `chunk_type`
- Inspect the chunk's underlying `DocItem` type from Docling:
  - `DocItemLabel.TEXT` → `"text"`
  - `DocItemLabel.TABLE` → `"table"`
  - `DocItemLabel.SECTION_HEADER` / heading items → `"heading"`
  - `DocItemLabel.CODE` → `"code"`
- If the chunk is a merge of multiple items, classify based on the dominant type

##### How to Extract `page_number`
- From `chunk.meta.doc_items` → each item has `prov` (provenance) info
- `prov[0].page_no` gives the page number (1-indexed)
- For chunks spanning multiple pages, use the first page

##### How to Build `parent_chunk_id`
- The `meta.headings` list provides the heading hierarchy
- The parent chunk is the chunk representing the immediate parent heading
- Generate deterministic IDs using: `hash(source_document + heading_text + heading_level)`
- If the chunk is a top-level item (no parent heading), `parent_chunk_id` = `null`

---

### 3. `backend/src/finbot/ingestion/metadata_builder.py`

#### Purpose
Transform raw Docling chunks into enriched chunks with full RBAC metadata, producing the final schema required for Qdrant storage.

#### Required Chunk Metadata Schema

```python
{
    "source_document": str,       # Filename of the source document
    "collection": str,            # One of: general, finance, engineering, marketing, hr
    "access_roles": list[str],    # Roles that can access this chunk
    "section_title": str,         # Heading under which this chunk falls
    "page_number": int,           # Page number in source document
    "chunk_type": str,            # One of: text, table, heading, code
    "parent_chunk_id": str | None,# ID of parent section chunk
    "chunk_id": str               # Unique ID for this chunk
}
```

#### Class: `MetadataBuilder`

##### Constructor
- Accept `FOLDER_RBAC_MAP` configuration (from settings)
- Define the folder-to-collection mapping

##### Method: `build_metadata(chunk, file_path: Path, chunk_index: int) → ChunkWithMetadata`

**Step-by-step logic:**

1. **Extract `source_document`:**
   - `file_path.name` → e.g., `"quarterly_report_Q1.pdf"`

2. **Derive `collection`:**
   - Determine which subfolder of `data/` the file resides in
   - `file_path.parent.name` → e.g., `"finance"`
   - Validate against known collection names
   - If unknown, default to `"general"`

3. **Look up `access_roles`:**
   - Use `FOLDER_RBAC_MAP[collection]` to get the list of roles
   - e.g., `"finance"` → `["finance_analyst", "executive"]`

4. **Extract `section_title`:**
   - From `chunk.meta.headings` — take the last (most specific) heading
   - If no headings, use `"Untitled Section"`

5. **Extract `page_number`:**
   - From chunk provenance metadata
   - Default to `1` if not available (e.g., for Markdown files)

6. **Determine `chunk_type`:**
   - Inspect the Docling item type (as described in chunker section)
   - Map to one of: `"text"`, `"table"`, `"heading"`, `"code"`

7. **Generate `chunk_id`:**
   - Use UUID v5 with namespace based on: `source_document + collection + chunk_index`
   - Ensures deterministic, reproducible IDs for re-ingestion

8. **Resolve `parent_chunk_id`:**
   - If `chunk.meta.headings` has entries, the parent is the chunk representing the second-to-last heading
   - Generate parent ID using same UUID v5 scheme
   - If top-level chunk, set to `None`

##### Method: `build_batch(chunks, file_path) → list[ChunkWithMetadata]`
- Iterate over chunks with index
- Call `build_metadata()` for each
- Return the complete list

#### Data Class: `ChunkWithMetadata`
- Fields: `text`, `chunk_id`, `metadata` (dict with all the schema fields above)
- This is the object passed to the uploader

---

### 4. `backend/src/finbot/ingestion/uploader.py`

#### Purpose
Embed the enriched chunks and upload them to Qdrant with their metadata payloads as filterable fields.

#### Class: `QdrantUploader`

##### Constructor
- Accept `Embedder` instance (from `retrieval/embedder.py`)
- Accept `VectorStore` instance (from `retrieval/vector_store.py`)
- Accept configuration: collection name, batch size

##### Method: `upload(chunks: list[ChunkWithMetadata]) → UploadResult`

**Step-by-step logic:**

1. **Ensure collection exists:**
   - Call `vector_store.create_collection_if_not_exists()` with proper vector size and distance metric

2. **Batch embed:**
   - Extract text from all chunks
   - Call `embedder.embed_batch(texts)` to get vectors
   - Batch size recommendation: 64-128 chunks per batch

3. **Build Qdrant points:**
   - For each chunk, create a Qdrant `PointStruct` with:
     - `id`: UUID from chunk_id
     - `vector`: the embedding vector
     - `payload`: the metadata dict (all fields from schema)
     - Include the raw `text` in payload for retrieval display

4. **Upsert to Qdrant:**
   - Call `vector_store.upsert(points)` in batches
   - Handle partial failures (log failed points, continue with rest)

5. **Create payload indexes** (for efficient filtering):
   - Index on `collection` (keyword)
   - Index on `access_roles` (keyword, array)
   - Index on `chunk_type` (keyword)
   - These indexes enable fast metadata filtering during RBAC retrieval

6. **Return `UploadResult`:**
   - Total chunks processed
   - Successfully uploaded count
   - Failed count with error details

##### Qdrant Collection Configuration
- **Vector size:** Match embedding model dimension (1536 for `text-embedding-3-small`, 384 for `all-MiniLM-L6-v2`)
- **Distance metric:** Cosine
- **On-disk storage:** Enable for large datasets
- **Payload indexes:** keyword index on `collection`, `access_roles`, `chunk_type`

---

### 5. `backend/scripts/ingest.py`

#### Purpose
CLI entry point that orchestrates the full ingestion pipeline.

#### CLI Arguments
| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--data-dir` | Path | `../../data` | Root data directory |
| `--collections` | list[str] | `all` | Which collections to ingest (e.g., `finance engineering`) |
| `--batch-size` | int | `64` | Embedding batch size |
| `--recreate` | flag | `False` | Drop and recreate Qdrant collection |
| `--dry-run` | flag | `False` | Parse and chunk but don't upload |

#### Execution Flow

```
1. Parse CLI arguments
2. Load settings from .env
3. Initialize components:
   ├── DocumentParser
   ├── HierarchicalDocumentChunker
   ├── MetadataBuilder
   ├── Embedder
   ├── VectorStore
   └── QdrantUploader
4. For each collection folder in data_dir:
   ├── Skip if not in --collections filter
   ├── Scan for supported documents
   ├── For each document:
   │   ├── Parse with DocumentParser
   │   ├── Chunk with HierarchicalDocumentChunker
   │   ├── Build metadata with MetadataBuilder
   │   └── Collect all chunks
   └── Upload batch with QdrantUploader
5. Print summary report:
   ├── Documents processed per collection
   ├── Total chunks created
   ├── Chunks per type (text, table, heading, code)
   └── Any errors encountered
```

---

## Key Design Decisions

### Why Docling?
- **Unified API:** Single library handles PDF, DOCX, MD, CSV, PPTX
- **Structural awareness:** Preserves headings, tables, code blocks as typed elements
- **Hierarchical chunking:** Built-in chunker that respects document structure
- **Table handling:** Extracts tables as structured data, not flattened text
- **Open source:** IBM's Docling is actively maintained and well-documented

### Why Hierarchical Chunking?
- **Context preservation:** Each chunk carries its heading context, improving retrieval quality
- **Parent-child relationships:** Enables "zoom in/zoom out" retrieval strategies
- **Structural typing:** Knowing a chunk is a table vs. text allows type-specific prompting
- **Better than fixed-size:** Respects semantic boundaries instead of arbitrary character counts

### Why Folder-Based RBAC Assignment?
- **Simplicity:** No need for a separate metadata file or database—the folder structure IS the access policy
- **Intuitive for admins:** Put a Finance document in `data/finance/` and it automatically gets correct access roles
- **Consistent with FOLDER_RBAC_MAP:** Direct 1:1 mapping from folder name to collection and roles

---

## Testing Strategy

### Unit Tests (`tests/test_ingestion/`)

#### `test_parser.py`
- Test parsing each supported format (PDF, DOCX, MD, CSV)
- Test error handling for unsupported formats
- Test error handling for corrupt files
- Test that parsed document contains expected structural elements

#### `test_chunker.py`
- Test chunking produces non-empty results
- Test heading hierarchy is preserved in chunk metadata
- Test tables are chunked as single items
- Test code blocks remain intact
- Test `chunk_type` classification accuracy

#### `test_metadata.py`
- Test `collection` derivation from file path
- Test `access_roles` lookup from FOLDER_RBAC_MAP
- Test `section_title` extraction from headings
- Test `chunk_id` determinism (same input → same ID)
- Test `parent_chunk_id` resolution
- Test default handling (no headings, no page numbers)

### Integration Test
- End-to-end test: place a test document → run ingestion → verify chunks in Qdrant
- Verify metadata filters work: search with role filter and confirm correct results

---

## Dependencies

```toml
[tool.poetry.dependencies]
docling = "^2.x"
docling-core = "^2.x"
qdrant-client = "^1.x"
openai = "^1.x"
```

---

> **Next:** Proceed to `03_semantic_routing.md` for Task 2.
