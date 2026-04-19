# Step 3: Semantic Query Routing (Task 2)

## Objective
Build a multi-route semantic query classifier using the **`semantic-router`** library that intelligently directs user queries to the appropriate department collection, while respecting RBAC constraints based on the user's role.

---

## Overview

```
User Query: "What was our Q1 revenue?"
        │
        ▼
┌──────────────────────────┐
│    SemanticRouter         │
│    (semantic-router lib)  │
│                          │
│  Routes:                 │
│  ├── finance_route       │──→ "finance" collection
│  ├── engineering_route   │──→ "engineering" collection
│  ├── marketing_route     │──→ "marketing" collection
│  ├── hr_general_route    │──→ "hr" collection
│  └── cross_department    │──→ all accessible collections
│                          │
│  Encoder:                │
│  └── OpenAI / HuggingFace│
└─────────┬────────────────┘
          │
          ▼
┌──────────────────────────┐
│    RBAC Filter            │
│                          │
│  User role: "engineer"   │
│  Classified: "finance"   │
│  Access: DENIED          │
│  Fallback: "general"    │
│  only (accessible)       │
└──────────────────────────┘
```

---

## Files to Implement

### 1. `backend/src/finbot/routing/routes.py`

#### Purpose
Define the 5 semantic routes, each with a minimum of 10 representative utterances. These utterances train the router to classify incoming queries.

#### Route Definitions

##### `finance_route`
**Description:** Queries about revenue, budgets, financial metrics, investor information, financial planning, and accounting.

**Representative Utterances (minimum 10):**
1. "What was our total revenue last quarter?"
2. "Show me the budget allocation for 2026"
3. "What are the key financial metrics from the annual report?"
4. "How much did we spend on R&D last year?"
5. "What is our current burn rate?"
6. "Can you summarize the investor presentation highlights?"
7. "What were the profit margins by product line?"
8. "How does our revenue compare quarter over quarter?"
9. "What are the projected expenses for next fiscal year?"
10. "Summarize the latest earnings call key takeaways"
11. "What is our debt-to-equity ratio?"
12. "Break down the operating costs by department"

**Target Collection:** `"finance"`
**Required Roles:** `["finance_analyst", "executive"]`

---

##### `engineering_route`
**Description:** Queries about systems architecture, APIs, technical incidents, code, infrastructure, and engineering processes.

**Representative Utterances (minimum 10):**
1. "Explain the microservices architecture overview"
2. "What APIs are available for the payment service?"
3. "Summarize the recent production incident report"
4. "What is our deployment pipeline process?"
5. "How is the authentication system designed?"
6. "What technology stack do we use for the backend?"
7. "List the API endpoints for the user management service"
8. "What were the root causes of the last outage?"
9. "Describe the database schema for the orders table"
10. "What are our system reliability SLAs?"
11. "How do we handle API rate limiting?"
12. "What is the disaster recovery plan for our infrastructure?"

**Target Collection:** `"engineering"`
**Required Roles:** `["engineer", "executive"]`

---

##### `marketing_route`
**Description:** Queries about marketing campaigns, brand strategy, market share, competitors, customer segments, and advertising.

**Representative Utterances (minimum 10):**
1. "What were the results of our Q1 marketing campaign?"
2. "Summarize the brand guidelines for social media"
3. "How has our market share changed over the last year?"
4. "What are the key takeaways from the competitor analysis?"
5. "Describe our target customer segments"
6. "What was the ROI on the last digital ad campaign?"
7. "What is our content marketing strategy for this quarter?"
8. "How is our brand perceived compared to competitors?"
9. "What channels drive the most customer acquisition?"
10. "Summarize the latest customer satisfaction survey results"
11. "What is our social media engagement rate trend?"
12. "What marketing budget was allocated for product launches?"

**Target Collection:** `"marketing"`
**Required Roles:** `["marketing_specialist", "executive"]`

---

##### `hr_general_route`
**Description:** Queries about HR policies, leave management, employee benefits, company culture, onboarding, and compliance.

**Representative Utterances (minimum 10):**
1. "What is the company's leave policy?"
2. "How do I apply for parental leave?"
3. "What health benefits are available to employees?"
4. "Describe the employee onboarding process"
5. "What is the company's remote work policy?"
6. "How does the performance review process work?"
7. "What are the guidelines for reporting workplace harassment?"
8. "What professional development programs are available?"
9. "Explain the company's code of conduct"
10. "How many sick days am I entitled to per year?"
11. "What is the process for requesting a role transfer?"
12. "What diversity and inclusion initiatives does the company have?"

**Target Collection:** `"hr"`
**Required Roles:** `["hr_representative", "executive"]`

---

##### `cross_department_route`
**Description:** Broad queries that span multiple departments or don't clearly belong to one domain. These should search all collections the user has access to.

**Representative Utterances (minimum 10):**
1. "Give me an overview of the company's performance this year"
2. "What are the company's strategic priorities for 2026?"
3. "Summarize the company handbook"
4. "What are the most important updates across all departments?"
5. "How is the company doing overall?"
6. "What are the key initiatives planned for next quarter?"
7. "Tell me about the company's mission and values"
8. "What changes were announced in the last all-hands meeting?"
9. "How does our company compare to industry benchmarks?"
10. "What are the upcoming company-wide events?"
11. "Summarize the CEO's quarterly message"
12. "What new policies were introduced this year?"

**Target Collections:** All collections accessible to the user's role
**Required Roles:** All roles (this is the catch-all route)

---

#### Route Object Structure
Each route should be defined as a `semantic-router` `Route` object:

```
Route(
    name="finance_route",
    utterances=[...list of 10+ utterances...],
    metadata={
        "target_collection": "finance",
        "required_roles": ["finance_analyst", "executive"],
        "description": "Financial queries"
    }
)
```

---

### 2. `backend/src/finbot/routing/router.py`

#### Purpose
Initialize the `SemanticRouter` with the 5 defined routes and provide a RBAC-aware query classification method.

#### Class: `QueryRouter`

##### Constructor
- Initialize the encoder:
  - **Option A:** `OpenAIEncoder(name="text-embedding-3-small")` — uses OpenAI embeddings for route matching
  - **Option B:** `HuggingFaceEncoder(name="all-MiniLM-L6-v2")` — local, no API cost
  - Choice should match the embedding model used for document ingestion (consistency)
- Load route definitions from `routes.py`
- Create `SemanticRouter(encoder=encoder, routes=[...])` — this is the `RouteLayer` in semantic-router
- The router automatically computes embeddings for all route utterances on initialization

##### Method: `classify(query: str, user_role: str) → RouteResult`

**Step-by-step logic:**

1. **Route the query:**
   - Call `router(query)` to get the classified route
   - Returns a `RouteChoice` with name and similarity score

2. **Handle no match (None route):**
   - If the router returns no match (query doesn't fit any route), default to `cross_department_route`
   - Log warning: "Query did not match any specific route, defaulting to cross-department"

3. **RBAC enforcement:**
   - Get the `required_roles` from the matched route's metadata
   - Check if `user_role` is in `required_roles`
   - **If allowed:** Return the route result with the target collection(s)
   - **If denied:** 
     - Log: "User role '{role}' not permitted for route '{route_name}', falling back to accessible collections"
     - Fall back to searching only the collections the user has access to
     - Determine accessible collections using `FOLDER_RBAC_MAP`

4. **Build target collections list:**
   - For a specific route: `[route.metadata["target_collection"]]`
   - For cross-department or fallback: `get_accessible_collections(user_role)`
   - Always include `"general"` (all roles have access)

5. **Return `RouteResult`:**
   ```
   RouteResult(
       route_name: str,           # Name of the matched route
       target_collections: list[str],  # Collections to search
       confidence: float,         # Router's similarity score
       was_rbac_filtered: bool,   # True if original route was denied
       original_route: str | None # If RBAC filtered, the original route name
   )
   ```

##### Method: `get_accessible_collections(role: str) → list[str]`
- Look up `FOLDER_RBAC_MAP` — find all collections where the role appears in the access list
- Always returns at least `["general"]`
- Example: `get_accessible_collections("engineer")` → `["general", "engineering"]`

##### Method: `get_route_info() → dict`
- Returns metadata about all configured routes for debugging / admin panel
- Includes route names, utterance counts, target collections

---

## RBAC + Routing Interaction Matrix

| User Role | finance_route | engineering_route | marketing_route | hr_general_route | cross_department_route |
|-----------|:---:|:---:|:---:|:---:|:---:|
| employee | ✗ → general only | ✗ → general only | ✗ → general only | ✗ → general only | general |
| finance_analyst | ✓ → finance | ✗ → general only | ✗ → general only | ✗ → general only | general, finance |
| engineer | ✗ → general only | ✓ → engineering | ✗ → general only | ✗ → general only | general, engineering |
| marketing_specialist | ✗ → general only | ✗ → general only | ✓ → marketing | ✗ → general only | general, marketing |
| hr_representative | ✗ → general only | ✗ → general only | ✗ → general only | ✓ → hr | general, hr |
| executive | ✓ → finance | ✓ → engineering | ✓ → marketing | ✓ → hr | all collections |

**Key:** ✓ = access granted, route proceeds normally. ✗ = access denied, falls back to accessible collections.

---

## How `semantic-router` Works Internally

1. **Initialization:**
   - Each route's utterances are embedded using the chosen encoder
   - Embeddings are stored in a local index (in-memory by default)

2. **Query classification:**
   - The user's query is embedded using the same encoder
   - Cosine similarity is computed against all route embeddings
   - The route with the highest similarity score is selected
   - If the score is below a threshold, no route is matched (returns `None`)

3. **Threshold tuning:**
   - The `SemanticRouter` has a configurable `aggregation` method (default: mean)
   - You can adjust the route-level `score_threshold` for each route
   - Recommend starting with default thresholds and tuning based on evaluation

---

## Configuration Points

| Parameter | Location | Description |
|-----------|----------|-------------|
| `ROUTER_ENCODER` | `settings.py` | Which encoder to use: `"openai"` or `"huggingface"` |
| `ROUTER_ENCODER_MODEL` | `settings.py` | Model name for the encoder |
| `ROUTER_SCORE_THRESHOLD` | `settings.py` | Minimum score for a route match (default: 0.3) |
| Route utterances | `routes.py` | The training utterances for each route |

---

## Testing Strategy

### Unit Tests (`tests/test_routing/test_router.py`)

#### Route Definition Tests
- Verify all 5 routes are defined
- Verify each route has ≥ 10 utterances
- Verify each route has correct metadata (target_collection, required_roles)

#### Classification Tests
- Test clear finance query → `finance_route`
- Test clear engineering query → `engineering_route`
- Test clear marketing query → `marketing_route`
- Test clear HR query → `hr_general_route`
- Test ambiguous query → `cross_department_route`
- Test nonsense query → defaults to `cross_department_route`

#### RBAC Filter Tests
- Test `employee` asking finance question → falls back to general
- Test `finance_analyst` asking finance question → proceeds to finance
- Test `executive` asking any question → proceeds to correct route (has all access)
- Test `engineer` asking HR question → falls back to general + engineering
- Verify `was_rbac_filtered` flag is set correctly

#### Accessible Collections Tests
- Test `get_accessible_collections("employee")` → `["general"]`
- Test `get_accessible_collections("executive")` → all 5 collections
- Test `get_accessible_collections("finance_analyst")` → `["general", "finance"]`

---

## Dependencies

```toml
[tool.poetry.dependencies]
semantic-router = "^0.1.x"
# The encoder deps come from semantic-router extras:
# semantic-router[openai] for OpenAI encoder
# semantic-router[local] for HuggingFace encoder
```

---

## Integration with Retrieval

The `RouteResult.target_collections` output feeds directly into the `RBACRetriever`:

```
1. User sends query with role
2. QueryRouter.classify(query, role) → RouteResult
3. RBACRetriever.retrieve(
       query, 
       role, 
       target_collections=route_result.target_collections
   )
4. Qdrant search with filters:
   - collection IN target_collections
   - access_roles CONTAINS user_role
```

This dual-layer filtering (route-level + retrieval-level) ensures defense-in-depth RBAC enforcement.

---

> **Next:** Proceed to `04_guardrails.md` for Task 3.
