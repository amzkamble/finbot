# Step 5: RAGAS Evaluation (Task 4)

## Objective
Build a comprehensive evaluation pipeline using the **RAGAS** framework to measure RAG pipeline quality across faithfulness, relevancy, context precision, and RBAC compliance.

---

## Overview

```
┌────────────────────────────┐
│     Test Dataset            │
│  (questions, ground truth,  │
│   expected roles/routes)    │
└──────────┬─────────────────┘
           │
           ▼
┌────────────────────────────┐
│   Evaluation Runner         │
│                            │
│  For each test case:       │
│  1. Run RAG pipeline       │
│  2. Collect:               │
│     - Query                │
│     - Retrieved contexts   │
│     - Generated answer     │
│     - Ground truth answer  │
│  3. Compute RAGAS metrics  │
│  4. Run RBAC-specific tests│
└──────────┬─────────────────┘
           │
           ▼
┌────────────────────────────┐
│   Results & Reports        │
│                            │
│  - Per-metric scores       │
│  - Per-collection scores   │
│  - Per-route accuracy      │
│  - RBAC compliance rate    │
│  - Detailed failure cases  │
└────────────────────────────┘
```

---

## Files to Implement

### 1. `backend/src/finbot/evaluation/dataset.py`

#### Purpose
Manage test datasets for RAGAS evaluation — loading, creation, and formatting into RAGAS-compatible structures.

#### Class: `EvaluationDataset`

##### Constructor
- Accept path to test set directory (`evaluation/test_sets/`)
- Load and validate test set files

##### Test Case Schema
Each test case is a JSON object:

```json
{
    "question": "What was the total revenue in Q1 2026?",
    "ground_truth": "The total revenue in Q1 2026 was $45.2 million, representing a 12% increase year-over-year.",
    "expected_collection": "finance",
    "expected_route": "finance_route",
    "test_roles": {
        "finance_analyst": "should_answer",
        "engineer": "should_deny_or_fallback",
        "executive": "should_answer"
    },
    "metadata": {
        "difficulty": "easy",
        "requires_table": false,
        "multi_hop": false
    }
}
```

##### Method: `load_test_set(collection: str | None) → list[TestCase]`
- Load test cases from JSON files
- If collection specified, load only that collection's test set
- If None, load all test sets

##### Method: `to_ragas_dataset(test_cases, rag_results) → Dataset`
- Convert test cases + RAG pipeline results into RAGAS-compatible `Dataset`
- Required columns for RAGAS:
  - `question`: the user query
  - `answer`: the generated answer from the RAG pipeline
  - `contexts`: list of retrieved context strings
  - `ground_truth`: the expected correct answer
- Return HuggingFace `Dataset` object

##### Method: `create_test_set_template(collection: str) → dict`
- Generate a template JSON file for a collection
- Pre-fill with the correct expected_collection and suggested test_roles

---

### 2. Test Set Specifications

#### `evaluation/test_sets/finance_test_set.json`
- **Minimum 15 test cases** covering:
  - Revenue and income queries (3-4 cases)
  - Budget and expense queries (3-4 cases)
  - Financial ratios and metrics (3-4 cases)
  - Investor-related queries (2-3 cases)
  - Table-based queries (e.g., "compare Q1 vs Q2 revenue") (2-3 cases)
- Each case must have `ground_truth` based on actual ingested documents
- Mix of easy, medium, and hard difficulty levels

#### `evaluation/test_sets/engineering_test_set.json`
- **Minimum 15 test cases** covering:
  - Architecture and design queries (3-4 cases)
  - API documentation queries (3-4 cases)
  - Incident/outage report queries (3-4 cases)
  - Infrastructure and deployment queries (2-3 cases)
  - Code-related queries (2-3 cases)

#### `evaluation/test_sets/marketing_test_set.json`
- **Minimum 15 test cases** covering:
  - Campaign performance queries (3-4 cases)
  - Brand and strategy queries (3-4 cases)
  - Market share and competitor queries (3-4 cases)
  - Customer segment queries (2-3 cases)
  - Budget and ROI queries (2-3 cases)

#### `evaluation/test_sets/hr_test_set.json`
- **Minimum 15 test cases** covering:
  - Leave policy queries (3-4 cases)
  - Benefits and compensation queries (3-4 cases)
  - Company culture and values (3-4 cases)
  - Compliance and conduct queries (2-3 cases)
  - Onboarding queries (2-3 cases)

#### `evaluation/test_sets/cross_department_test_set.json`
- **Minimum 10 test cases** covering:
  - Company-wide performance queries (3-4 cases)
  - Multi-department comparison queries (3-4 cases)
  - General company knowledge queries (3-4 cases)

#### `evaluation/rbac_test_matrix.json`
A specialized test set focused purely on RBAC enforcement:

```json
{
    "rbac_tests": [
        {
            "question": "What was Q1 revenue?",
            "role": "engineer",
            "expected_behavior": "should_not_return_finance_data",
            "expected_collections_searched": ["general", "engineering"]
        },
        {
            "question": "What was Q1 revenue?",
            "role": "finance_analyst",
            "expected_behavior": "should_return_finance_data",
            "expected_collections_searched": ["finance"]
        },
        {
            "question": "What was Q1 revenue?",
            "role": "executive",
            "expected_behavior": "should_return_finance_data",
            "expected_collections_searched": ["finance"]
        }
    ]
}
```

- Cover all 6 roles × 5 collections = 30 access scenarios
- Test both allow and deny cases

---

### 3. `backend/src/finbot/evaluation/evaluate.py`

#### Purpose
Orchestrate the full RAGAS evaluation: run the RAG pipeline over test cases, compute metrics, and generate reports.

#### Class: `RAGEvaluator`

##### Constructor
- Accept:
  - RAG pipeline instance (the full chain: route → retrieve → generate)
  - RAGAS metrics to evaluate
  - Output directory for results
- Initialize RAGAS evaluation configuration

##### RAGAS Metrics to Implement

| Metric | What It Measures | RAGAS Class |
|--------|-----------------|-------------|
| **Faithfulness** | Whether the answer is factually consistent with the retrieved contexts | `faithfulness` |
| **Answer Relevancy** | Whether the answer is relevant to the question | `answer_relevancy` |
| **Context Precision** | Whether the retrieved contexts are relevant to the question | `context_precision` |
| **Context Recall** | Whether all relevant information is retrieved | `context_recall` |
| **Answer Correctness** | How close the answer is to the ground truth | `answer_correctness` |
| **Answer Similarity** | Semantic similarity between answer and ground truth | `answer_similarity` |

##### Method: `run_pipeline_on_test_set(test_cases: list[TestCase], role: str) → list[RAGResult]`

**For each test case:**
1. Set the user role for the pipeline
2. Run the full RAG pipeline:
   - Input guardrails (skip rate limiting for evaluation)
   - Semantic routing
   - RBAC-filtered retrieval
   - LLM generation
   - Output guardrails (skip citation enforcement for raw evaluation)
3. Collect results:
   ```
   RAGResult(
       question: str,
       answer: str,
       contexts: list[str],       # Retrieved context texts
       ground_truth: str,
       route_used: str,
       collections_searched: list[str],
       guardrail_flags: list[str],
       latency_ms: float
   )
   ```

##### Method: `evaluate(test_cases, role) → EvaluationReport`

**Step-by-step:**
1. Run pipeline on test set → `list[RAGResult]`
2. Convert to RAGAS dataset format
3. Call `ragas.evaluate()` with configured metrics
4. Parse RAGAS results
5. Compute additional custom metrics (see below)
6. Generate `EvaluationReport`

##### Method: `evaluate_rbac_compliance(rbac_test_matrix) → RBACReport`

**Custom RBAC-specific evaluation:**
1. For each test in the RBAC matrix:
   - Run the pipeline with the specified role
   - Check if the retrieved contexts come from expected/allowed collections
   - Check if denied collections are never searched
2. Compute:
   - **RBAC Compliance Rate:** % of cases where access control was correctly enforced
   - **False Positive Rate:** % of cases where access was granted when it shouldn't have been
   - **False Negative Rate:** % of cases where access was denied when it should have been
3. Generate per-role and per-collection compliance reports

##### Custom Metrics (Beyond RAGAS)

| Metric | What It Measures | How to Compute |
|--------|-----------------|----------------|
| **Route Accuracy** | Whether the semantic router selected the correct route | Compare `route_used` with `expected_route` from test case |
| **RBAC Compliance** | Whether retrieval correctly filtered by role | Check collections searched vs. expected |
| **Citation Coverage** | Whether sources are properly cited | Count citations in answer vs. retrieved chunks |
| **Guardrail Trigger Rate** | How often guardrails fire on legitimate queries | Count false-positive guardrail blocks |
| **Latency P50/P95/P99** | Response time distribution | Percentile analysis of `latency_ms` |

---

### 4. Evaluation Report Format

#### `EvaluationReport` Structure

```json
{
    "timestamp": "2026-04-18T00:00:00Z",
    "model": "gpt-4o-mini",
    "embedding_model": "text-embedding-3-small",
    "total_test_cases": 70,
    
    "ragas_metrics": {
        "faithfulness": 0.87,
        "answer_relevancy": 0.82,
        "context_precision": 0.78,
        "context_recall": 0.75,
        "answer_correctness": 0.80,
        "answer_similarity": 0.85
    },
    
    "per_collection_metrics": {
        "finance": {"faithfulness": 0.90, "answer_relevancy": 0.85, ...},
        "engineering": {"faithfulness": 0.85, "answer_relevancy": 0.80, ...},
        ...
    },
    
    "routing_metrics": {
        "overall_accuracy": 0.92,
        "per_route_accuracy": {
            "finance_route": 0.95,
            "engineering_route": 0.90,
            ...
        }
    },
    
    "rbac_metrics": {
        "compliance_rate": 1.0,
        "false_positive_rate": 0.0,
        "false_negative_rate": 0.0,
        "per_role_results": {...}
    },
    
    "performance_metrics": {
        "latency_p50_ms": 1200,
        "latency_p95_ms": 2500,
        "latency_p99_ms": 4000
    },
    
    "failure_cases": [
        {
            "question": "...",
            "expected": "...",
            "actual": "...",
            "failure_type": "low_faithfulness",
            "score": 0.3
        }
    ]
}
```

---

### 5. `backend/scripts/evaluate.py`

#### Purpose
CLI entry point for running evaluations.

#### CLI Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--test-dir` | Path | `../../evaluation/test_sets` | Test set directory |
| `--collections` | list[str] | `all` | Which collections to evaluate |
| `--role` | str | `executive` | Role to use (executive sees all) |
| `--output-dir` | Path | `../../evaluation/results` | Output directory for reports |
| `--metrics` | list[str] | `all` | Which RAGAS metrics to compute |
| `--include-rbac` | flag | `True` | Include RBAC compliance testing |
| `--verbose` | flag | `False` | Print detailed per-question results |

#### Execution Flow

```
1. Parse CLI arguments
2. Load settings
3. Initialize RAG pipeline components
4. Load test sets
5. Run evaluation:
   a. Standard RAGAS evaluation (per collection)
   b. RBAC compliance evaluation (per role)
   c. Routing accuracy evaluation
6. Generate reports:
   a. JSON report (machine-readable)
   b. Console summary (human-readable table)
   c. Failure cases log
7. Save reports to output directory
```

#### Console Output Example

```
═══════════════════════════════════════════════════
  FinBot RAG Evaluation Report - 2026-04-18
═══════════════════════════════════════════════════

  RAGAS Metrics (Overall)
  ─────────────────────────────────────────────
  Faithfulness       : 0.87  ████████▋  
  Answer Relevancy   : 0.82  ████████▏  
  Context Precision  : 0.78  ███████▊   
  Context Recall     : 0.75  ███████▌   
  Answer Correctness : 0.80  ████████   

  Routing Accuracy   : 92.0%
  RBAC Compliance    : 100.0%
  
  Per Collection Breakdown
  ─────────────────────────────────────────────
  Collection    │ Faith │ Relev │ Prec  │ Recall
  finance       │ 0.90  │ 0.85  │ 0.82  │ 0.78
  engineering   │ 0.85  │ 0.80  │ 0.75  │ 0.72
  marketing     │ 0.88  │ 0.83  │ 0.80  │ 0.76
  hr            │ 0.86  │ 0.81  │ 0.77  │ 0.74
  
  ⚠ 5 failure cases logged to results/failures.json
═══════════════════════════════════════════════════
```

---

## Evaluation Workflow

### Step 1: Prepare Test Data
1. Ingest all documents into Qdrant (Task 1 must be complete)
2. Manually craft test cases based on actual document content
3. Write ground truth answers by referring to the source documents

### Step 2: Run Standard Evaluation
```bash
python -m scripts.evaluate --collections all --role executive
```
This gives baseline metrics for the full pipeline.

### Step 3: Run Per-Role Evaluation
```bash
python -m scripts.evaluate --role employee
python -m scripts.evaluate --role finance_analyst
python -m scripts.evaluate --role engineer
```
Compare metrics across roles to ensure quality doesn't degrade for restricted roles.

### Step 4: Run RBAC Compliance Test
```bash
python -m scripts.evaluate --include-rbac --verbose
```
Verify that every role × collection combination is correctly enforced.

### Step 5: Analyze Results
- Review failure cases
- Identify patterns (e.g., low faithfulness on table-based queries)
- Tune retrieval parameters, prompts, or chunking strategy
- Re-run evaluation after changes

---

## Iteration Strategy

| Issue | Potential Fix |
|-------|-------------|
| Low faithfulness | Improve retrieval (more chunks, better embeddings), refine prompt |
| Low context precision | Tune chunk size, improve routing utterances |
| Low context recall | Increase retrieval top-k, add cross-department fallback |
| Poor routing accuracy | Add more utterances to misclassified routes |
| RBAC violations | Fix metadata filters, verify chunk metadata |
| High latency | Reduce chunk count, optimize embedding batch size |

---

## Dependencies

```toml
[tool.poetry.dependencies]
ragas = "^0.2.x"
datasets = "^3.x"     # HuggingFace datasets (required by RAGAS)
```

---

> **Next:** Proceed to `06_fullstack_app.md` for Task 5.
