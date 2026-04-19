# FinBot — RAG + RBAC Intelligent Finance Chatbot

## Executive Summary

FinBot is a **production-grade Retrieval-Augmented Generation (RAG)** chatbot with **Role-Based Access Control (RBAC)** that serves multiple departments—Finance, Engineering, Marketing, and HR—while enforcing strict data isolation based on user roles. It combines document intelligence, semantic query routing, LLM guardrails, and a modern full-stack interface.

---

## High-Level Architecture

```
                         ┌──────────────────────────────┐
                         │     Next.js Frontend          │
                         │  ┌────────┬───────┬────────┐  │
                         │  │ Login  │ Chat  │ Admin  │  │
                         │  └────┬───┴───┬───┴────┬───┘  │
                         └───────┼───────┼────────┼──────┘
                                 │       │        │
                         ════════╪═══════╪════════╪══════════
                                 ▼       ▼        ▼
                         ┌──────────────────────────────┐
                         │     FastAPI Backend            │
                         │                                │
                         │  ┌─────────────────────────┐   │
                         │  │   Auth & RBAC Middleware │   │
                         │  └────────────┬────────────┘   │
                         │               ▼                │
                         │  ┌─────────────────────────┐   │
                         │  │   Input Guardrails       │   │
                         │  │  • Off-topic detection   │   │
                         │  │  • Prompt injection      │   │
                         │  │  • PII scrubbing         │   │
                         │  │  • Rate limiting         │   │
                         │  └────────────┬────────────┘   │
                         │               ▼                │
                         │  ┌─────────────────────────┐   │
                         │  │   Semantic Router        │   │
                         │  │  (5 query routes)        │   │
                         │  └────────────┬────────────┘   │
                         │               ▼                │
                         │  ┌─────────────────────────┐   │
                         │  │  RBAC-Filtered Retriever │   │
                         │  │  (Qdrant + metadata)     │   │
                         │  └────────────┬────────────┘   │
                         │               ▼                │
                         │  ┌─────────────────────────┐   │
                         │  │   LLM Generator          │   │
                         │  └────────────┬────────────┘   │
                         │               ▼                │
                         │  ┌─────────────────────────┐   │
                         │  │   Output Guardrails      │   │
                         │  │  • Grounding check       │   │
                         │  │  • Cross-role leakage    │   │
                         │  │  • Source citation        │   │
                         │  └─────────────────────────┘   │
                         └──────────────────────────────┘
                                        │
                         ┌──────────────┼──────────────┐
                         │              ▼              │
                         │  ┌─────────────────────┐    │
                         │  │  Qdrant Vector DB   │    │
                         │  └─────────────────────┘    │
                         │                             │
                         │  ┌─────────────────────┐    │
                         │  │  Docling Ingestion  │    │
                         │  └─────────────────────┘    │
                         │                             │
                         │  ┌─────────────────────┐    │
                         │  │  RAGAS Evaluation   │    │
                         │  └─────────────────────┘    │
                         └─────────────────────────────┘
```

---

## Task Breakdown

| # | Task | Description | Plan File |
|---|------|-------------|-----------|
| 1 | Document Ingestion | Docling-based multi-format parsing with hierarchical chunking & RBAC metadata | `01_project_structure.md`, `02_document_ingestion.md` |
| 2 | Semantic Routing | Multi-route query classifier using `semantic-router` with 5 department routes | `03_semantic_routing.md` |
| 3 | Guardrails | LangChain-based input/output guardrails for safety, grounding, and compliance | `04_guardrails.md` |
| 4 | RAGAS Evaluation | End-to-end RAG pipeline evaluation with faithfulness, relevancy, and RBAC metrics | `05_ragas_evaluation.md` |
| 5 | Full-Stack Application | Next.js frontend + FastAPI backend with login, chat, admin panel, RBAC enforcement | `06_fullstack_app.md` |

---

## RBAC Model

```
FOLDER_RBAC_MAP = {
    "general":     ["employee", "finance_analyst", "engineer", "marketing_specialist", "executive", "hr_representative"],
    "finance":     ["finance_analyst", "executive"],
    "engineering": ["engineer", "executive"],
    "marketing":   ["marketing_specialist", "executive"],
    "hr":          ["hr_representative", "executive"]
}
```

**Key Principle:** Every chunk carries `access_roles` metadata. At retrieval time, the vector search applies a **metadata filter** so users only ever see documents their role permits.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Document Parsing | Docling (IBM) |
| Chunking | Docling Hierarchical Chunker |
| Embeddings | OpenAI `text-embedding-3-small` or HuggingFace `all-MiniLM-L6-v2` |
| Vector Store | Qdrant |
| Query Routing | `semantic-router` |
| LLM | OpenAI GPT-4o / GPT-4o-mini |
| Guardrails | LangChain Guardrails + custom validators |
| Evaluation | RAGAS |
| Backend | FastAPI (Python 3.11+) |
| Frontend | Next.js 14+ (App Router) |
| Auth | JWT-based with role claims |
| Containerization | Docker + Docker Compose |

---

## Repository Structure (Production-Grade)

```
finance_bot/
├── backend/                        # Python backend (FastAPI)
│   ├── src/
│   │   └── finbot/
│   │       ├── __init__.py
│   │       ├── config/             # Centralized configuration
│   │       ├── ingestion/          # Task 1: Document ingestion pipeline
│   │       ├── routing/            # Task 2: Semantic query routing
│   │       ├── guardrails/         # Task 3: Input/output guardrails
│   │       ├── retrieval/          # RBAC-filtered vector retrieval
│   │       ├── generation/         # LLM response generation
│   │       ├── evaluation/         # Task 4: RAGAS evaluation
│   │       ├── auth/               # Authentication & RBAC
│   │       ├── api/                # FastAPI routes & middleware
│   │       ├── models/             # Pydantic schemas
│   │       └── utils/              # Shared utilities
│   ├── tests/
│   ├── scripts/                    # CLI scripts (ingest, evaluate)
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                       # Task 5: Next.js application
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   └── styles/
│   ├── package.json
│   └── Dockerfile
├── data/                           # Source documents (by department)
│   ├── general/
│   ├── finance/
│   ├── engineering/
│   ├── marketing/
│   └── hr/
├── evaluation/                     # RAGAS test sets & results
├── docker-compose.yml
├── .env.example
└── README.md
```

> See `01_project_structure.md` for the complete file-by-file breakdown.

---

## Implementation Order & Dependencies

```
Phase 1: Foundation (Day 1)
  └── Project Structure & Config

Phase 2: Task 1 — Ingestion (Days 2-7)
  ├── Docling Parser Module
  ├── Hierarchical Chunker
  ├── Metadata Builder & RBAC Tags
  ├── Qdrant Uploader
  └── Ingestion CLI

Phase 3: Task 2 — Routing (Days 8-10)
  ├── Route Definitions (5 routes)
  ├── Semantic Router Integration
  └── RBAC-Aware Route Resolution

Phase 4: Task 3 — Guardrails (Days 11-14)
  ├── Input Guardrails
  └── Output Guardrails

Phase 5: Task 4 — Evaluation (Days 15-17)
  ├── RAGAS Test Dataset
  └── Evaluation Pipeline

Phase 6: Task 5 — Full-Stack App (Days 8-17, parallel)
  ├── FastAPI Backend & Auth
  ├── Next.js Login & Chat UI
  ├── Admin Panel
  └── Integration & E2E Testing
```

> **Note:** Task 5 (Full-Stack App) can begin in parallel with Task 2 once Task 1 is complete, as the backend API layer and frontend can be scaffolded independently.

---

## Plan Files Index

| File | Purpose |
|------|---------|
| `00_overview.md` | This file — high-level summary |
| `01_project_structure.md` | Complete repository structure with every file's purpose |
| `02_document_ingestion.md` | Task 1 — Docling parsing, hierarchical chunking, metadata, Qdrant upload |
| `03_semantic_routing.md` | Task 2 — Semantic Router with 5 query routes + RBAC enforcement |
| `04_guardrails.md` | Task 3 — Input & output guardrails using LangChain |
| `05_ragas_evaluation.md` | Task 4 — RAGAS evaluation pipeline & metrics |
| `06_fullstack_app.md` | Task 5 — Next.js + FastAPI full-stack app with RBAC UI |

---

> **Next Step:** Read each plan file in order (01 → 06) for detailed implementation guidance.
