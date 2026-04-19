# Step 1: Project Structure — Complete File-by-File Breakdown

This document defines every file and directory in the production repository, explaining **what** each file does, **why** it exists, and **what** it should contain.

---

## Root Directory

```
finance_bot/
├── backend/
├── frontend/
├── data/
├── evaluation/
├── plan/                           # This planning documentation
├── docker-compose.yml              # Orchestrates all services
├── .env.example                    # Template for environment variables
├── .gitignore
└── README.md                       # Project documentation
```

### `.env.example`
- Contains all environment variable keys with placeholder values
- Variables needed:
  - `OPENAI_API_KEY` — LLM and embedding API key
  - `QDRANT_HOST` / `QDRANT_PORT` — Vector DB connection
  - `QDRANT_COLLECTION_NAME` — Default collection name
  - `JWT_SECRET_KEY` — For signing auth tokens
  - `JWT_ALGORITHM` — e.g., HS256
  - `EMBEDDING_MODEL` — e.g., `text-embedding-3-small`
  - `LLM_MODEL` — e.g., `gpt-4o-mini`
  - `LOG_LEVEL` — e.g., `INFO`

### `docker-compose.yml`
- Services to define:
  - `qdrant` — Qdrant vector database (official image)
  - `backend` — FastAPI application (from `backend/Dockerfile`)
  - `frontend` — Next.js application (from `frontend/Dockerfile`)
- Network: shared bridge network for inter-service communication
- Volumes: persistent volume for Qdrant data

---

## Data Directory

```
data/
├── general/
│   ├── company_handbook.pdf
│   ├── onboarding_guide.md
│   └── faq.docx
├── finance/
│   ├── quarterly_report_Q1.pdf
│   ├── budget_2026.csv
│   └── investor_presentation.pdf
├── engineering/
│   ├── architecture_overview.md
│   ├── api_documentation.pdf
│   └── incident_reports.docx
├── marketing/
│   ├── campaign_results_Q1.csv
│   ├── brand_guidelines.pdf
│   └── competitor_analysis.md
└── hr/
    ├── leave_policy.pdf
    ├── benefits_guide.docx
    └── code_of_conduct.md
```

### Purpose
- Each subfolder name maps directly to a **collection** in the RBAC model
- The folder name automatically assigns `collection` and `access_roles` metadata to all documents within it
- Supports mixed formats: `.pdf`, `.md`, `.docx`, `.csv`
- Users should place their department-specific documents in the appropriate folder before running ingestion

### How RBAC Maps to Folders

| Folder | Collection | Roles with Access |
|--------|-----------|-------------------|
| `general/` | general | employee, finance_analyst, engineer, marketing_specialist, executive, hr_representative |
| `finance/` | finance | finance_analyst, executive |
| `engineering/` | engineering | engineer, executive |
| `marketing/` | marketing | marketing_specialist, executive |
| `hr/` | hr | hr_representative, executive |

---

## Backend Directory — Complete Structure

```
backend/
├── src/
│   └── finbot/
│       ├── __init__.py
│       │
│       ├── config/
│       │   ├── __init__.py
│       │   └── settings.py
│       │
│       ├── ingestion/
│       │   ├── __init__.py
│       │   ├── parser.py
│       │   ├── chunker.py
│       │   ├── metadata_builder.py
│       │   └── uploader.py
│       │
│       ├── routing/
│       │   ├── __init__.py
│       │   ├── routes.py
│       │   └── router.py
│       │
│       ├── guardrails/
│       │   ├── __init__.py
│       │   ├── input_guards.py
│       │   └── output_guards.py
│       │
│       ├── retrieval/
│       │   ├── __init__.py
│       │   ├── embedder.py
│       │   ├── vector_store.py
│       │   └── rbac_retriever.py
│       │
│       ├── generation/
│       │   ├── __init__.py
│       │   ├── llm_client.py
│       │   ├── prompts.py
│       │   └── chain.py
│       │
│       ├── evaluation/
│       │   ├── __init__.py
│       │   ├── dataset.py
│       │   └── evaluate.py
│       │
│       ├── auth/
│       │   ├── __init__.py
│       │   ├── jwt_handler.py
│       │   ├── rbac.py
│       │   └── models.py
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── app.py
│       │   ├── middleware.py
│       │   ├── deps.py
│       │   └── routes/
│       │       ├── __init__.py
│       │       ├── auth_routes.py
│       │       ├── chat_routes.py
│       │       └── admin_routes.py
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── requests.py
│       │   └── responses.py
│       │
│       └── utils/
│           ├── __init__.py
│           ├── logger.py
│           └── exceptions.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_ingestion/
│   │   ├── __init__.py
│   │   ├── test_parser.py
│   │   ├── test_chunker.py
│   │   └── test_metadata.py
│   ├── test_routing/
│   │   ├── __init__.py
│   │   └── test_router.py
│   ├── test_guardrails/
│   │   ├── __init__.py
│   │   ├── test_input_guards.py
│   │   └── test_output_guards.py
│   ├── test_retrieval/
│   │   ├── __init__.py
│   │   └── test_rbac_retriever.py
│   ├── test_auth/
│   │   ├── __init__.py
│   │   └── test_rbac.py
│   └── test_api/
│       ├── __init__.py
│       └── test_chat.py
│
├── scripts/
│   ├── ingest.py                   # CLI: bulk document ingestion
│   ├── evaluate.py                 # CLI: run RAGAS evaluation
│   └── seed_users.py              # CLI: seed demo users
│
├── pyproject.toml                  # Project metadata & dependencies
├── Dockerfile
└── README.md
```

---

## Backend File Descriptions

### `config/`

#### `settings.py`
- **What:** Centralized application configuration using Pydantic `BaseSettings`
- **Why:** Single source of truth for all env vars, avoids scattered `os.getenv()` calls
- **Contains:**
  - Pydantic `Settings` class with fields for all environment variables
  - Validation and type coercion for config values
  - `FOLDER_RBAC_MAP` constant definition
  - Embedding model, LLM model, Qdrant connection settings
  - JWT settings (secret, algorithm, expiry)

---

### `ingestion/`

> Detailed in `02_document_ingestion.md`

#### `parser.py`
- **What:** Wraps IBM Docling for multi-format document conversion
- **Contains:** `DocumentParser` class with `parse(file_path) → DoclingDocument` method
- **Supports:** PDF, DOCX, MD, CSV, PPTX

#### `chunker.py`
- **What:** Implements hierarchical chunking using Docling's `HierarchicalChunker`
- **Contains:** `HierarchicalDocumentChunker` class that produces chunks with parent-child relationships
- **Key:** Preserves heading hierarchy, tables as separate chunks, code blocks

#### `metadata_builder.py`
- **What:** Builds RBAC-compliant metadata for each chunk
- **Contains:** `MetadataBuilder` class that attaches `source_document`, `collection`, `access_roles`, `section_title`, `page_number`, `chunk_type`, `parent_chunk_id`
- **Key:** Derives `collection` and `access_roles` from the folder the source document resides in

#### `uploader.py`
- **What:** Embeds chunks and upserts them to Qdrant with metadata payloads
- **Contains:** `QdrantUploader` class with `upload(chunks_with_metadata)` method
- **Key:** Creates collection if not exists, handles batch upserts

---

### `routing/`

> Detailed in `03_semantic_routing.md`

#### `routes.py`
- **What:** Defines the 5 semantic routes with their utterance samples
- **Contains:** `Route` objects for `finance_route`, `engineering_route`, `marketing_route`, `hr_general_route`, `cross_department_route`, each with 10+ utterances

#### `router.py`
- **What:** Initializes `SemanticRouter` and provides query classification with RBAC filtering
- **Contains:** `QueryRouter` class with `classify(query, user_role) → RouteResult` method
- **Key:** If a user's role doesn't permit the classified route, falls back to cross-department (searching only accessible collections)

---

### `guardrails/`

> Detailed in `04_guardrails.md`

#### `input_guards.py`
- **What:** Pre-processing checks on user input before it enters the RAG pipeline
- **Contains:** Off-topic detector, prompt injection detector, PII scrubber, session rate limiter
- **Key:** Each guard returns a `GuardResult` with pass/fail status and reason

#### `output_guards.py`
- **What:** Post-processing checks on LLM output before returning to user
- **Contains:** Grounding checker (against retrieved contexts), cross-role leakage detector, source citation enforcer
- **Key:** Can modify, flag, or block the response

---

### `retrieval/`

#### `embedder.py`
- **What:** Wrapper around the embedding model (OpenAI or HuggingFace)
- **Contains:** `Embedder` class with `embed(text) → list[float]` and `embed_batch(texts) → list[list[float]]`
- **Key:** Abstraction allows swapping embedding providers

#### `vector_store.py`
- **What:** Qdrant client wrapper for collection management and search
- **Contains:** `VectorStore` class with `create_collection()`, `upsert()`, `search()` methods
- **Key:** Low-level Qdrant operations

#### `rbac_retriever.py`
- **What:** Orchestrates RBAC-filtered retrieval
- **Contains:** `RBACRetriever` class with `retrieve(query, user_role, target_collections) → list[RetrievedChunk]`
- **How it works:**
  1. Receives target collections from the Semantic Router
  2. Embeds the query
  3. Searches Qdrant with metadata filter: `access_roles` must contain user's role
  4. Returns ranked chunks with full metadata

---

### `generation/`

#### `llm_client.py`
- **What:** Wrapper around the LLM API (OpenAI)
- **Contains:** `LLMClient` class with `generate(prompt, context) → str`
- **Key:** Handles streaming, token counting, error handling

#### `prompts.py`
- **What:** Stores all prompt templates
- **Contains:** RAG system prompt, guardrail prompts, evaluation prompts
- **Key:** Uses LangChain `PromptTemplate` or `ChatPromptTemplate`

#### `chain.py`
- **What:** Composes the full RAG chain
- **Contains:** `RAGChain` class that wires together retriever → prompt → LLM → output parser
- **Key:** Accepts pre-processed query (post-guardrails) and returns structured response

---

### `auth/`

#### `jwt_handler.py`
- **What:** JWT token creation and validation
- **Contains:** `create_access_token(user_data)`, `decode_token(token)`, token expiry management
- **Key:** Token payload includes `user_id`, `username`, `role`

#### `rbac.py`
- **What:** RBAC enforcement logic
- **Contains:** `get_accessible_collections(role) → list[str]` using `FOLDER_RBAC_MAP`, `check_access(role, collection) → bool`
- **Key:** Central authority for all access control decisions

#### `models.py`
- **What:** User data models
- **Contains:** `User` Pydantic model, demo user definitions with pre-assigned roles

---

### `api/`

#### `app.py`
- **What:** FastAPI application factory
- **Contains:** `create_app()` function, CORS setup, router registration, startup/shutdown events
- **Key:** Initializes all dependencies (Qdrant client, Router, etc.) on startup

#### `middleware.py`
- **What:** Custom middleware
- **Contains:** Request logging middleware, JWT authentication middleware, rate limiting middleware
- **Key:** Extracts user from JWT and attaches to request state

#### `deps.py`
- **What:** FastAPI dependency injection
- **Contains:** `get_current_user()`, `get_qdrant_client()`, `get_router()`, `get_settings()`
- **Key:** Provides clean dependency injection for route handlers

#### `routes/auth_routes.py`
- **What:** Login and authentication endpoints
- **Contains:** `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/refresh`

#### `routes/chat_routes.py`
- **What:** Chat/query endpoints
- **Contains:** `POST /api/chat` — the main RAG endpoint that runs the full pipeline
- **Flow:** Authenticate → Input Guardrails → Route → Retrieve → Generate → Output Guardrails → Respond

#### `routes/admin_routes.py`
- **What:** Admin panel endpoints
- **Contains:** `GET /api/admin/users`, `PUT /api/admin/users/{id}/role`, `GET /api/admin/documents`, `POST /api/admin/ingest`
- **Key:** Restricted to `executive` role

---

### `models/`

#### `requests.py`
- **What:** Pydantic models for API request bodies
- **Contains:** `ChatRequest`, `LoginRequest`, `IngestRequest`, etc.

#### `responses.py`
- **What:** Pydantic models for API response bodies
- **Contains:** `ChatResponse` (with answer, sources, route, guardrail_flags), `LoginResponse`, `UserResponse`, etc.

---

### `utils/`

#### `logger.py`
- **What:** Structured logging configuration
- **Contains:** Logger factory with JSON formatting, log levels, correlation IDs
- **Key:** Each module gets its own logger: `logger = get_logger(__name__)`

#### `exceptions.py`
- **What:** Custom exception classes and handlers
- **Contains:** `RBACAccessDenied`, `GuardrailTriggered`, `RateLimitExceeded`, etc.
- **Key:** Registered as FastAPI exception handlers for clean error responses

---

### `scripts/`

#### `ingest.py`
- **What:** CLI tool for bulk document ingestion
- **Usage:** `python -m scripts.ingest --data-dir ../data --collection all`
- **Flow:** Scan data dir → parse each doc → chunk → build metadata → upload to Qdrant

#### `evaluate.py`
- **What:** CLI tool for running RAGAS evaluation
- **Usage:** `python -m scripts.evaluate --test-set ../evaluation/test_set.json --output ../evaluation/results/`

#### `seed_users.py`
- **What:** Seeds demo users for testing
- **Creates:** One user per role: `employee`, `finance_analyst`, `engineer`, `marketing_specialist`, `executive`, `hr_representative`

---

### `pyproject.toml`
- **Required dependencies:**
  - `fastapi`, `uvicorn[standard]`
  - `docling`, `docling-core`
  - `semantic-router`
  - `langchain`, `langchain-openai`, `langchain-community`
  - `qdrant-client`
  - `openai`
  - `ragas`
  - `pydantic`, `pydantic-settings`
  - `python-jose[cryptography]` (JWT)
  - `python-multipart`
- **Dev dependencies:**
  - `pytest`, `pytest-asyncio`, `httpx` (for testing)
  - `ruff` (linting)
  - `mypy` (type checking)

---

## Frontend Directory — Complete Structure

> Detailed in `06_fullstack_app.md`

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx              # Root layout with providers
│   │   ├── page.tsx                # Redirect to /login
│   │   ├── globals.css             # Global styles
│   │   ├── login/
│   │   │   └── page.tsx            # Login page
│   │   ├── chat/
│   │   │   └── page.tsx            # Chat interface
│   │   └── admin/
│   │       └── page.tsx            # Admin panel
│   │
│   ├── components/
│   │   ├── ui/                     # Reusable UI primitives
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Badge.tsx
│   │   │   ├── Modal.tsx
│   │   │   └── Spinner.tsx
│   │   ├── chat/
│   │   │   ├── ChatWindow.tsx      # Main chat container
│   │   │   ├── MessageBubble.tsx   # Individual message display
│   │   │   ├── SourceCitation.tsx  # Citation display component
│   │   │   ├── RouteIndicator.tsx  # Shows which route was used
│   │   │   └── GuardrailBanner.tsx # Warning banner for guardrails
│   │   ├── admin/
│   │   │   ├── UserTable.tsx       # User management table
│   │   │   ├── DocumentList.tsx    # Document management
│   │   │   └── RoleEditor.tsx      # Role assignment UI
│   │   └── auth/
│   │       └── LoginForm.tsx       # Login form component
│   │
│   ├── lib/
│   │   ├── api.ts                  # API client (fetch wrapper)
│   │   ├── auth.ts                 # Auth context & hooks
│   │   └── types.ts                # TypeScript interfaces
│   │
│   └── styles/
│       └── theme.css               # Design tokens & CSS variables
│
├── public/
│   └── logo.svg
├── package.json
├── tsconfig.json
├── next.config.js
└── Dockerfile
```

---

## Evaluation Directory

```
evaluation/
├── test_sets/
│   ├── finance_test_set.json       # Q&A pairs for finance domain
│   ├── engineering_test_set.json
│   ├── marketing_test_set.json
│   ├── hr_test_set.json
│   └── cross_department_test_set.json
├── results/                        # Generated evaluation reports
│   └── .gitkeep
└── rbac_test_matrix.json           # Role × collection access test cases
```

---

> **Next:** Proceed to `02_document_ingestion.md` for Task 1 detailed implementation.
