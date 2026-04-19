# Step 6: Full-Stack Application (Task 5)

## Objective
Build a **Next.js chat application** with a **Python FastAPI backend** that demonstrates the full RAG + RBAC system, including a login screen, chat interface, and admin panel.

---

## Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js Frontend                      │
│                                                         │
│  ┌─────────────┐  ┌─────────────────┐  ┌────────────┐   │
│  │  /login     │  │  /chat          │  │  /admin    │   │
│  │             │  │                 │  │            │   │
│  │ Role-based  │  │ Chat messages   │  │ User mgmt  │   │
│  │ demo login  │  │ Source citations│  │ Doc mgmt   │   │
│  │             │  │ Route indicator │  │ Role editor│   │
│  │             │  │ Guardrail warns │  │ Ingest UI  │   │
│  │             │  │ Role status bar │  │            │   │
│  └─────────────┘  └─────────────────┘  └────────────┘   │
│                                                         │
│  Auth Context (JWT) │ API Client │ Role-Based Routing    │
└──────────┬──────────────────────────────────────────────┘
           │ HTTP/REST (JSON)
           ▼
┌─────────────────────────────────────────────────────────┐
│                 FastAPI Backend                           │
│                                                         │
│  Endpoints:                                              │
│  ├── POST /api/auth/login                               │
│  ├── GET  /api/auth/me                                  │
│  ├── POST /api/chat                                     │
│  ├── GET  /api/chat/history                             │
│  ├── GET  /api/admin/users                              │
│  ├── PUT  /api/admin/users/{id}/role                    │
│  ├── GET  /api/admin/documents                          │
│  └── POST /api/admin/ingest                             │
│                                                         │
│  Middleware: CORS, JWT Auth, Request Logging             │
└─────────────────────────────────────────────────────────┘
```

---

## Part A: FastAPI Backend

### File: `backend/src/finbot/api/app.py`

#### Purpose
FastAPI application factory — the main entry point that wires everything together.

#### Application Factory: `create_app() → FastAPI`

**Setup responsibilities:**
1. Create FastAPI instance with metadata (title, description, version)
2. Configure CORS middleware (allow frontend origin)
3. Register all route routers:
   - `/api/auth` → auth_routes
   - `/api/chat` → chat_routes
   - `/api/admin` → admin_routes
4. Register startup event:
   - Initialize Qdrant client and verify connection
   - Initialize SemanticRouter (pre-compute route embeddings)
   - Initialize Embedder
   - Initialize LLM client
   - Initialize guardrail pipelines
5. Register shutdown event:
   - Close Qdrant connection
6. Register exception handlers for custom exceptions

#### Run Configuration
- Host: `0.0.0.0`, Port: `8000`
- Reload: `True` in development
- Workers: `1` (for in-memory rate limiting; use Redis for multi-worker)

---

### File: `backend/src/finbot/api/middleware.py`

#### Purpose
Custom middleware for cross-cutting concerns.

#### Middleware 1: `JWTAuthMiddleware`
- Extract `Authorization: Bearer <token>` from request headers
- Decode and validate JWT token
- Attach `user` object to `request.state.user`
- Skip for public routes: `/api/auth/login`, `/docs`, `/openapi.json`
- Return `401 Unauthorized` for invalid/expired tokens

#### Middleware 2: `RequestLoggingMiddleware`
- Log every request: method, path, user_id, response_status, latency_ms
- Format as structured JSON for log aggregation
- Mask sensitive data (passwords, tokens)

---

### File: `backend/src/finbot/api/deps.py`

#### Purpose
FastAPI dependency injection functions.

#### Dependencies to Define

| Dependency | Returns | Used By |
|-----------|---------|---------|
| `get_current_user()` | `User` | All authenticated routes |
| `require_role(role)` | `User` | Admin routes (require "executive") |
| `get_settings()` | `Settings` | All components |
| `get_qdrant_client()` | `QdrantClient` | Retrieval routes |
| `get_query_router()` | `QueryRouter` | Chat routes |
| `get_input_guardrails()` | `InputGuardrailPipeline` | Chat routes |
| `get_output_guardrails()` | `OutputGuardrailPipeline` | Chat routes |
| `get_rag_chain()` | `RAGChain` | Chat routes |

---

### File: `backend/src/finbot/api/routes/auth_routes.py`

#### Endpoints

##### `POST /api/auth/login`
- **Request Body:** `{ "username": str, "password": str }`
- **Logic:**
  1. Look up user in demo user store
  2. Verify password (simple comparison for demo; use hashing in production)
  3. Generate JWT token with claims: `{ user_id, username, role, exp }`
  4. Return `{ token, user: { id, username, role } }`
- **Response:** `LoginResponse`

##### `GET /api/auth/me`
- **Auth:** Required (JWT)
- **Logic:** Return current user info from token
- **Response:** `UserResponse`

##### Demo Users to Seed

| Username | Password | Role |
|----------|----------|------|
| `john_employee` | `demo123` | employee |
| `sarah_finance` | `demo123` | finance_analyst |
| `mike_engineer` | `demo123` | engineer |
| `lisa_marketing` | `demo123` | marketing_specialist |
| `alex_executive` | `demo123` | executive |
| `emma_hr` | `demo123` | hr_representative |

---

### File: `backend/src/finbot/api/routes/chat_routes.py`

#### Endpoints

##### `POST /api/chat`
The **core endpoint** — runs the complete RAG pipeline.

- **Auth:** Required (JWT)
- **Request Body:**
  ```
  {
      "message": str,          # User's query
      "session_id": str        # For rate limiting and history
  }
  ```
- **Full Pipeline Flow:**
  1. Extract user from JWT → get role
  2. **Input Guardrails:**
     - Rate limiting (by session_id)
     - Prompt injection check
     - PII scrubbing
     - Off-topic detection
     - If blocked → return `ChatResponse` with `blocked=True`, `blocked_reason`
  3. **Semantic Routing:**
     - Classify the (cleaned) query
     - Get target collections based on route + RBAC
  4. **RBAC-Filtered Retrieval:**
     - Search Qdrant with `collection IN target_collections AND access_roles CONTAINS user_role`
     - Return top-k chunks with metadata
  5. **LLM Generation:**
     - Build prompt with retrieved contexts
     - Generate response with citations
  6. **Output Guardrails:**
     - Cross-role leakage check
     - Grounding check
     - Source citation enforcement
  7. **Return response**

- **Response:** `ChatResponse`
  ```json
  {
      "answer": "The Q1 revenue was $45.2M...",
      "sources": [
          {
              "document": "quarterly_report_Q1.pdf",
              "page": 5,
              "section": "Revenue Overview",
              "collection": "finance",
              "chunk_type": "text"
          }
      ],
      "route": {
          "name": "finance_route",
          "confidence": 0.92,
          "was_rbac_filtered": false
      },
      "guardrails": {
          "input": {
              "pii_scrubbed": false,
              "off_topic_score": 0.1
          },
          "output": {
              "grounding_score": 0.95,
              "grounding_warning": false,
              "citations_valid": true
          }
      },
      "metadata": {
          "latency_ms": 1250,
          "collections_searched": ["finance"],
          "chunks_retrieved": 5
      }
  }
  ```

##### `GET /api/chat/history`
- **Auth:** Required
- **Query Params:** `session_id`, `limit` (default 50)
- **Logic:** Return chat history for the session (stored in memory or simple DB)
- **Response:** List of messages with timestamps

---

### File: `backend/src/finbot/api/routes/admin_routes.py`

#### Access Control
All admin endpoints require `executive` role. Other roles get `403 Forbidden`.

#### Endpoints

##### `GET /api/admin/users`
- List all users with their roles and last activity
- **Response:** `list[UserResponse]`

##### `PUT /api/admin/users/{user_id}/role`
- Update a user's role
- **Request Body:** `{ "role": str }`
- Validate role is one of the 6 defined roles
- **Response:** Updated `UserResponse`

##### `GET /api/admin/documents`
- List all ingested documents with metadata
- Query Qdrant for distinct `source_document` values
- Group by collection
- **Response:** `list[DocumentInfo]` with `{ filename, collection, chunk_count, access_roles }`

##### `POST /api/admin/ingest`
- Trigger document ingestion for a specific collection
- **Request Body:** `{ "collection": str }` or `{ "collection": "all" }`
- Runs the ingestion pipeline asynchronously
- Returns a job ID for status checking
- **Response:** `{ "job_id": str, "status": "started" }`

##### `GET /api/admin/stats`
- Dashboard statistics
- **Response:**
  ```json
  {
      "total_documents": 15,
      "total_chunks": 1250,
      "chunks_by_collection": {"finance": 350, ...},
      "chunks_by_type": {"text": 900, "table": 200, ...},
      "total_users": 6,
      "users_by_role": {"executive": 1, ...}
  }
  ```

---

### File: `backend/src/finbot/models/requests.py`

#### Pydantic Request Models

| Model | Fields |
|-------|--------|
| `LoginRequest` | `username: str`, `password: str` |
| `ChatRequest` | `message: str`, `session_id: str` |
| `UpdateRoleRequest` | `role: str` (validated against allowed roles) |
| `IngestRequest` | `collection: str` (validated against known collections) |

---

### File: `backend/src/finbot/models/responses.py`

#### Pydantic Response Models

| Model | Key Fields |
|-------|-----------|
| `LoginResponse` | `token: str`, `user: UserResponse` |
| `UserResponse` | `id: str`, `username: str`, `role: str` |
| `ChatResponse` | `answer: str`, `sources: list[SourceInfo]`, `route: RouteInfo`, `guardrails: GuardrailInfo` |
| `SourceInfo` | `document: str`, `page: int`, `section: str`, `collection: str`, `chunk_type: str` |
| `RouteInfo` | `name: str`, `confidence: float`, `was_rbac_filtered: bool` |
| `GuardrailInfo` | `input: InputGuardInfo`, `output: OutputGuardInfo` |
| `DocumentInfo` | `filename: str`, `collection: str`, `chunk_count: int`, `access_roles: list[str]` |
| `StatsResponse` | `total_documents: int`, `total_chunks: int`, `chunks_by_collection: dict`, etc. |

---

## Part B: Next.js Frontend

### Technology Choices
- **Next.js 14+** with App Router
- **CSS Modules or Vanilla CSS** for styling (no Tailwind unless requested)
- **Fetch API** for HTTP requests (no extra library needed)
- **React Context** for auth state management
- **Design:** Dark mode, glassmorphism, premium feel, Inter/Outfit font

---

### File: `frontend/src/app/layout.tsx`

#### Purpose
Root layout with providers and global structure.

#### Responsibilities
- Import global CSS and Google Fonts (Inter or Outfit)
- Wrap children in `AuthProvider` context
- Set page metadata (title, description)
- Apply dark mode theme by default

---

### File: `frontend/src/app/login/page.tsx`

#### Login Screen Design & Features

##### Layout
- Centered card on a gradient/animated background
- Company logo at top
- Title: "FinBot — Intelligent Finance Assistant"
- Subtitle: "Select your role to explore department-specific access"

##### Demo User Selection
- Display 6 role cards/buttons (one per demo user)
- Each card shows:
  - Role name (e.g., "Finance Analyst")
  - Username
  - Brief description of what they can access
  - Icon/avatar for the role
- Clicking a card auto-fills the login form and logs in

##### Alternative Manual Login
- Username and password fields
- "Sign In" button
- Error display for invalid credentials

##### Visual Polish
- Animated gradient background
- Glassmorphism card effect
- Smooth hover animations on role cards
- Loading state on sign-in button

---

### File: `frontend/src/app/chat/page.tsx`

#### Chat Interface Design & Features

##### Header Bar
- FinBot logo + title
- Active role badge (e.g., "🔹 Finance Analyst")
- Accessible collections pills (e.g., "general", "finance")
- Logout button
- Link to Admin panel (visible only to executives)

##### Chat Area
- Full-height scrollable message container
- Messages displayed as bubbles:
  - **User messages:** Right-aligned, accent color
  - **Bot messages:** Left-aligned, darker card
- Markdown rendering for bot responses (headers, bold, lists, code blocks)
- Typing indicator animation while waiting for response

##### Source Citations Panel
Each bot message should display its sources below the answer:

```
┌─────────────────────────────────────────┐
│  📄 quarterly_report_Q1.pdf — Page 5    │
│  Section: "Revenue Overview"            │
│  Collection: finance                    │
│  Type: text                             │
└─────────────────────────────────────────┘
```

- Collapsible/expandable source cards
- Color-coded by collection (finance=green, engineering=blue, etc.)

##### Route Indicator
- Small badge or label above each bot response showing:
  - Route used: "via finance_route (92% confidence)"
  - Collections searched: "Searched: finance"
  - If RBAC filtered: "⚠ Route adjusted — original: engineering_route"

##### Guardrail Warning Banner
- If any output guardrail was triggered (flagged, not blocked):
  - Yellow warning banner at the top of the response
  - "⚠ This response may contain ungrounded claims (grounding score: 0.65)"
- If input was blocked:
  - Red banner replacing the response
  - "🚫 Query blocked: Prompt injection detected"

##### Input Area
- Text input field with send button
- Character count indicator
- Disable while loading
- Keyboard shortcut: Enter to send

##### Responsive Design
- Desktop: Full-width chat with sidebar for sources
- Mobile: Stack chat and sources vertically

---

### File: `frontend/src/app/admin/page.tsx`

#### Admin Panel Design & Features

**Access:** Only visible/accessible to users with `executive` role. Redirect others to `/chat`.

##### Tabs/Sections

**Tab 1: Users**
- Table of all users
- Columns: Username, Current Role, Last Active, Actions
- Actions: Dropdown to change role
- Role change should take effect on next user login/token refresh

**Tab 2: Documents**
- Table of ingested documents grouped by collection
- Columns: Filename, Collection, Chunks, Access Roles
- Color-coded collection badges
- "Re-ingest" button per collection

**Tab 3: System Stats**
- Dashboard cards:
  - Total documents / Total chunks
  - Chunks by collection (bar chart or pie chart)
  - Chunks by type (text / table / heading / code)
  - Users by role
- Use CSS-based charts or simple visual bars (no heavy chart libraries needed)

##### Visual Design
- Dark sidebar navigation
- Clean data tables with hover effects
- Status badges with colors
- Card-based stats with subtle gradients

---

### File: `frontend/src/components/chat/ChatWindow.tsx`

#### Purpose
Main chat container that manages message list and scroll behavior.

#### Features
- Auto-scroll to latest message
- Infinite scroll for history (lazy load older messages)
- Empty state: welcome message with suggested queries based on user's role
- Session management (generate UUID for session_id)

---

### File: `frontend/src/components/chat/MessageBubble.tsx`

#### Purpose
Render individual chat messages (both user and bot).

#### For Bot Messages
- Render markdown content (use a lightweight MD renderer)
- Display source citations (collapsible)
- Show route indicator badge
- Show guardrail warning if flagged
- Show metadata tooltip (latency, chunks retrieved)

#### For User Messages
- Simple text display
- Timestamp

---

### File: `frontend/src/components/chat/SourceCitation.tsx`

#### Purpose
Render a single source citation card.

#### Display
- Document filename (with document icon)
- Page number
- Section title
- Collection badge (color-coded)
- Chunk type badge

---

### File: `frontend/src/components/chat/RouteIndicator.tsx`

#### Purpose
Display semantic routing information for each response.

#### Display
- Route name badge
- Confidence percentage
- RBAC filter warning (if route was adjusted)
- Collections searched list

---

### File: `frontend/src/components/chat/GuardrailBanner.tsx`

#### Purpose
Display guardrail-related warnings/blocks.

#### Variants
- **Warning (yellow):** Low grounding score, PII was scrubbed
- **Blocked (red):** Prompt injection, off-topic, rate limited
- **Info (blue):** Citations were auto-added

---

### File: `frontend/src/lib/api.ts`

#### Purpose
Centralized API client for all backend communication.

#### Functions

| Function | Method | Endpoint | Description |
|----------|--------|----------|-------------|
| `login(username, password)` | POST | `/api/auth/login` | Authenticate user |
| `getMe()` | GET | `/api/auth/me` | Get current user info |
| `sendMessage(message, sessionId)` | POST | `/api/chat` | Send chat message |
| `getChatHistory(sessionId)` | GET | `/api/chat/history` | Load chat history |
| `getUsers()` | GET | `/api/admin/users` | List users (admin) |
| `updateRole(userId, role)` | PUT | `/api/admin/users/{id}/role` | Update role (admin) |
| `getDocuments()` | GET | `/api/admin/documents` | List documents (admin) |
| `triggerIngest(collection)` | POST | `/api/admin/ingest` | Trigger ingestion (admin) |
| `getStats()` | GET | `/api/admin/stats` | Get system stats (admin) |

#### Implementation Details
- Use `fetch()` with automatic JWT token injection from auth context
- Handle 401 responses by redirecting to login
- Handle 429 (rate limit) with user-friendly message
- Include request/response type safety

---

### File: `frontend/src/lib/auth.ts`

#### Purpose
React Context for authentication state.

#### Context Data
- `user: User | null`
- `token: string | null`
- `isAuthenticated: boolean`
- `isExecutive: boolean`
- `accessibleCollections: string[]`

#### Context Actions
- `login(username, password)` — authenticate and store token
- `logout()` — clear token and redirect to login
- `getToken()` — return current token for API calls

#### Token Storage
- Store JWT in `localStorage` for persistence across page refreshes
- Decode token client-side to get user info and role
- Check expiry before each API call

---

### File: `frontend/src/lib/types.ts`

#### Purpose
TypeScript interfaces matching the backend Pydantic models.

#### Interfaces to Define
- `User`, `LoginResponse`
- `ChatMessage`, `ChatResponse`
- `SourceInfo`, `RouteInfo`, `GuardrailInfo`
- `DocumentInfo`, `StatsResponse`

---

### File: `frontend/src/styles/theme.css`

#### Purpose
Design system tokens and CSS custom properties.

#### Design Tokens

```css
:root {
    /* Color Palette - Dark Theme */
    --bg-primary: #0a0a0f;
    --bg-secondary: #12121a;
    --bg-card: rgba(255, 255, 255, 0.05);
    --bg-glass: rgba(255, 255, 255, 0.08);
    
    /* Accent Colors */
    --accent-primary: #6366f1;      /* Indigo */
    --accent-secondary: #8b5cf6;    /* Violet */
    --accent-success: #10b981;      /* Emerald */
    --accent-warning: #f59e0b;      /* Amber */
    --accent-danger: #ef4444;       /* Red */
    
    /* Collection Colors */
    --color-finance: #10b981;
    --color-engineering: #3b82f6;
    --color-marketing: #f59e0b;
    --color-hr: #8b5cf6;
    --color-general: #6b7280;
    
    /* Typography */
    --font-family: 'Inter', 'Outfit', sans-serif;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    
    /* Spacing, Borders, Shadows */
    --radius-sm: 6px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --glass-border: 1px solid rgba(255, 255, 255, 0.1);
    --shadow-glass: 0 8px 32px rgba(0, 0, 0, 0.3);
    
    /* Animation */
    --transition-fast: 150ms ease;
    --transition-normal: 250ms ease;
}
```

---

## Docker Compose Configuration

### `docker-compose.yml`

#### Services

**1. `qdrant`**
- Image: `qdrant/qdrant:latest`
- Ports: `6333:6333`, `6334:6334`
- Volume: `qdrant_data:/qdrant/storage`

**2. `backend`**
- Build from: `./backend/Dockerfile`
- Ports: `8000:8000`
- Environment: from `.env` file
- Depends on: `qdrant`
- Health check: `GET /docs`

**3. `frontend`**
- Build from: `./frontend/Dockerfile`
- Ports: `3000:3000`
- Environment: `NEXT_PUBLIC_API_URL=http://backend:8000`
- Depends on: `backend`

#### Networks
- `finbot-network`: bridge network for inter-service communication

#### Volumes
- `qdrant_data`: persistent storage for vector data

---

## End-to-End User Flow

### Flow 1: Employee Login → Chat → Restricted Access

```
1. User selects "Employee" role on login page
2. JWT generated with role="employee"
3. Chat page shows: "Role: Employee | Access: general"
4. User asks: "What was the Q1 revenue?"
5. Semantic Router → finance_route
6. RBAC check → employee NOT in finance roles
7. Fallback → search only "general" collection
8. Response from general docs (may not have revenue details)
9. Route indicator: "⚠ Route adjusted (finance → general)"
10. Response: "Based on general company information..."
```

### Flow 2: Executive Login → Chat → Full Access

```
1. User selects "Executive" role on login page
2. JWT generated with role="executive"
3. Chat page shows: "Role: Executive | Access: all"
4. User asks: "What was the Q1 revenue?"
5. Semantic Router → finance_route
6. RBAC check → executive in finance roles → PASS
7. Search "finance" collection
8. Full financial data retrieved
9. Response with citations from quarterly report
10. Route indicator: "finance_route (95% confidence)"
```

### Flow 3: Executive → Admin Panel

```
1. Executive user sees "Admin" link in header
2. Users tab: view all 6 demo users
3. Documents tab: see ingested docs by collection
4. Change engineer's role to finance_analyst
5. Stats tab: view system overview
```

---

## Testing Strategy

### Backend API Tests (`tests/test_api/`)

#### `test_chat.py`
- Test unauthenticated request → 401
- Test normal chat flow → successful response with all fields
- Test rate limiting → 429 after limit
- Test prompt injection → blocked response
- Test RBAC: employee asking finance question → general fallback
- Test RBAC: executive asking finance question → finance data

#### `test_auth.py`
- Test valid login → token returned
- Test invalid credentials → 401
- Test token expiry
- Test /me endpoint returns correct user

#### `test_admin.py`
- Test non-executive access → 403
- Test executive access → success
- Test role update → role changed
- Test document listing → correct grouping

### Frontend Tests
- Manual testing via browser
- Verify login flow for each role
- Verify chat displays citations, routes, guardrails
- Verify admin panel is only accessible to executives
- Verify responsive design

---

## Dependencies

### Backend
```toml
[tool.poetry.dependencies]
fastapi = "^0.115.x"
uvicorn = { version = "^0.34.x", extras = ["standard"] }
python-jose = { version = "^3.x", extras = ["cryptography"] }
python-multipart = "^0.0.x"
pydantic-settings = "^2.x"
```

### Frontend
```json
{
    "dependencies": {
        "next": "^14.x",
        "react": "^18.x",
        "react-dom": "^18.x",
        "react-markdown": "^9.x"
    },
    "devDependencies": {
        "typescript": "^5.x",
        "@types/react": "^18.x",
        "@types/node": "^20.x"
    }
}
```

---

> **End of Implementation Plan**
> 
> Return to `00_overview.md` for the summary and roadmap.
