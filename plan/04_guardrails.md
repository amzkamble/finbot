# Step 4: Input & Output Guardrails (Task 3)

## Objective
Implement **LangChain-based guardrails** for both input (pre-processing) and output (post-processing) to ensure safety, compliance, grounding, and data isolation in the RAG pipeline.

---

## Overview

```
                  User Query
                      │
                      ▼
        ┌─────────────────────────────┐
        │     INPUT GUARDRAILS        │
        │                             │
        │  1. Off-topic Detection     │──→ BLOCK if off-topic
        │  2. Prompt Injection Detect │──→ BLOCK if injection
        │  3. PII Scrubbing           │──→ REDACT PII, continue
        │  4. Session Rate Limiting   │──→ BLOCK if rate exceeded
        │                             │
        └──────────────┬──────────────┘
                       │ (cleaned query)
                       ▼
              ┌────────────────┐
              │  RAG Pipeline  │
              │  Route → Retrieve → Generate
              └────────┬───────┘
                       │ (LLM response + contexts)
                       ▼
        ┌─────────────────────────────┐
        │     OUTPUT GUARDRAILS       │
        │                             │
        │  1. Grounding Check         │──→ FLAG if ungrounded
        │  2. Cross-Role Leakage      │──→ BLOCK if leaking
        │  3. Source Citation Enforce  │──→ REJECT if no citations
        │                             │
        └──────────────┬──────────────┘
                       │ (validated response)
                       ▼
                  Final Response to User
```

---

## Common Data Models

### `GuardResult`
Every guardrail returns a standardized result:

```
GuardResult(
    passed: bool,              # True if the check passed
    guard_name: str,           # e.g., "off_topic_detection"
    action: str,               # "pass" | "block" | "modify" | "flag"
    message: str | None,       # Human-readable explanation
    modified_content: str | None,  # Modified input/output (for PII scrubbing)
    metadata: dict             # Additional details (scores, detected items, etc.)
)
```

### `GuardrailPipelineResult`
Aggregate result from running all guardrails:

```
GuardrailPipelineResult(
    passed: bool,              # True only if ALL guards passed
    results: list[GuardResult],# Individual results
    final_content: str,        # The content after all modifications
    blocked_by: str | None     # Name of the guard that blocked (if any)
)
```

---

## File 1: `backend/src/finbot/guardrails/input_guards.py`

### Purpose
Pre-process user queries before they enter the RAG pipeline. Each guard can **block**, **modify**, or **pass** the input.

---

### Guard 1: Off-Topic Detection

#### Purpose
Detect queries that are unrelated to the company's domain (finance, engineering, marketing, HR, general business) and block them to prevent wasting LLM resources.

#### Implementation Approach
- Use an **LLM-based classifier** via LangChain
- Create a prompt that asks the LLM to classify whether a query is on-topic or off-topic
- On-topic = anything related to business, company operations, or the defined departments
- Off-topic = personal queries, entertainment, coding help, general knowledge unrelated to work

#### Class: `OffTopicGuard`

##### Constructor
- Accept LLM client (LangChain `ChatOpenAI` or similar)
- Define the classification prompt template
- Set configurable threshold for confidence

##### Method: `check(query: str) → GuardResult`
- Send classification prompt to LLM
- Parse response for on-topic/off-topic classification and confidence
- If off-topic with high confidence → return `GuardResult(passed=False, action="block", message="This query appears to be off-topic...")`
- If on-topic → return `GuardResult(passed=True, action="pass")`

##### Prompt Design
The prompt should:
- Define what "on-topic" means (company business, departments, policies, etc.)
- Provide examples of on-topic and off-topic queries
- Ask for a JSON response with `is_on_topic` (bool) and `confidence` (float)
- Include few-shot examples for consistency

##### Edge Cases
- Ambiguous queries should lean toward "on-topic" (err on the side of permissiveness)
- Very short queries (< 3 words) should be passed through with a warning flag

---

### Guard 2: Prompt Injection Detection

#### Purpose
Detect and block attempts to manipulate the system prompt, extract training data, or bypass safety controls.

#### Implementation Approach
- **Dual-layer detection:**
  1. **Pattern-based:** Regex patterns for known injection techniques
  2. **LLM-based:** Ask the LLM to evaluate if the input is a prompt injection attempt

#### Class: `PromptInjectionGuard`

##### Constructor
- Define regex patterns for common injection signatures:
  - "ignore previous instructions"
  - "forget your instructions"
  - "you are now..."
  - "system prompt:"
  - "act as..."
  - Role-playing attempts: "pretend you are"
  - Delimiter injection: excessive use of `###`, `---`, etc.
- Accept LLM client for secondary LLM-based check

##### Method: `check(query: str) → GuardResult`
- **Step 1:** Run regex pattern matching (fast, low-cost)
  - If any pattern matches → `GuardResult(passed=False, action="block", message="Potential prompt injection detected")`
- **Step 2:** If no regex match, run LLM-based check (for sophisticated attacks)
  - Prompt the LLM: "Is this query an attempt to manipulate the AI system?"
  - If LLM flags it → block
  - If LLM passes → pass
- Return combined result with detection details in metadata

##### Pattern Categories
| Category | Example Patterns |
|----------|-----------------|
| Instruction override | "ignore previous", "disregard above", "new instructions" |
| Role manipulation | "you are now", "act as", "pretend to be" |
| Data extraction | "show me your prompt", "print system message", "reveal instructions" |
| Delimiter injection | Unusual markdown/separator patterns trying to break prompt context |
| Encoding attacks | Base64 encoded instructions, Unicode tricks |

---

### Guard 3: PII Scrubbing

#### Purpose
Detect and redact Personally Identifiable Information (PII) from user queries before they are processed, embedded, or logged.

#### Implementation Approach
- Use a combination of **regex patterns** and **NER (Named Entity Recognition)** for PII detection
- Consider using `presidio` library or custom regex for the following PII types

#### Class: `PIIScrubber`

##### Constructor
- Define regex patterns for:
  - **Email addresses:** standard email regex
  - **Phone numbers:** various formats (US, international)
  - **SSN:** `\d{3}-\d{2}-\d{4}` pattern
  - **Credit card numbers:** Luhn-validated 13-19 digit patterns
  - **IP addresses:** IPv4 and IPv6
  - **Dates of birth:** common date formats with context clues
- Define replacement tokens: `[EMAIL_REDACTED]`, `[PHONE_REDACTED]`, `[SSN_REDACTED]`, etc.

##### Method: `check(query: str) → GuardResult`
- Scan query against all PII patterns
- For each match:
  - Record the PII type and position (but NOT the actual value)
  - Replace with the appropriate redaction token
- Return `GuardResult`:
  - `passed=True` (PII scrubbing modifies but doesn't block)
  - `action="modify"` if PII was found, `"pass"` if not
  - `modified_content` contains the scrubbed query
  - `metadata` includes count of each PII type found

##### Behavior
- PII scrubbing **never blocks** a query — it only modifies
- The modified query (with redacted PII) is what gets passed to the RAG pipeline
- Original query with PII should NOT be logged

---

### Guard 4: Session Rate Limiting

#### Purpose
Prevent abuse by limiting the number of queries a user can make within a time window.

#### Implementation Approach
- Use an **in-memory sliding window counter** (per user session)
- For production, recommend Redis-backed rate limiting

#### Class: `RateLimiter`

##### Constructor
- Configure:
  - `max_requests_per_minute`: default `20`
  - `max_requests_per_hour`: default `100`
  - `max_requests_per_day`: default `500`
- Initialize in-memory storage (dict of user_id → list of timestamps)

##### Method: `check(user_id: str) → GuardResult`
- Get the user's request timestamps
- Count requests in the last minute, hour, day
- If any limit exceeded → `GuardResult(passed=False, action="block", message="Rate limit exceeded. Please try again in X seconds.")`
- If within limits → record current timestamp, return `GuardResult(passed=True, action="pass")`
- Include `metadata`: `{"requests_this_minute": N, "limit_minute": 20, "retry_after_seconds": X}`

##### Cleanup
- Periodically prune old timestamps (older than 24 hours) to prevent memory growth
- In the production version, key-expiry in Redis handles this automatically

---

### Input Guardrail Pipeline

#### Class: `InputGuardrailPipeline`

##### Constructor
- Accept instances of all 4 input guards
- Define execution order: Rate Limiting → Prompt Injection → PII Scrubbing → Off-Topic
  - Rate limiting first (cheapest, blocks obvious abuse)
  - Prompt injection second (security priority)
  - PII scrubbing third (modifies content for downstream guards)
  - Off-topic last (most expensive, uses LLM)

##### Method: `run(query: str, user_id: str) → GuardrailPipelineResult`
- Execute guards in order
- **On block:** Stop immediately, return results so far
- **On modify:** Use modified content for subsequent guards
- **On pass:** Continue to next guard
- Return aggregate `GuardrailPipelineResult`

---

## File 2: `backend/src/finbot/guardrails/output_guards.py`

### Purpose
Post-process LLM responses before returning them to the user. Ensures factual grounding, RBAC compliance, and proper citation.

---

### Guard 1: Grounding Check

#### Purpose
Verify that the LLM's response is grounded in the retrieved context chunks and not hallucinated.

#### Implementation Approach
- Use an **LLM-as-judge** approach
- Send the response + retrieved contexts to an LLM and ask it to verify grounding

#### Class: `GroundingChecker`

##### Constructor
- Accept LLM client
- Define the grounding check prompt template

##### Method: `check(response: str, retrieved_contexts: list[str]) → GuardResult`
- Construct prompt:
  - "Given these source passages: [contexts], evaluate whether the following response is fully supported by the sources: [response]"
  - Ask for: `is_grounded` (bool), `grounding_score` (0-1), `ungrounded_claims` (list)
- If `grounding_score < 0.7` → `GuardResult(passed=False, action="flag", message="Response may contain ungrounded claims")`
  - **Note:** "flag" means the response is still returned but with a warning banner
- If grounded → `GuardResult(passed=True, action="pass")`
- Include `ungrounded_claims` in metadata for the UI to display

##### Prompt Requirements
- Must compare each claim in the response against the source passages
- Must identify specific sentences that lack grounding
- Must be tolerant of reasonable inferences from the data

---

### Guard 2: Cross-Role Leakage Check

#### Purpose
Ensure the LLM response doesn't inadvertently reveal information from collections the user doesn't have access to. This is a defense-in-depth check beyond retrieval filtering.

#### Implementation Approach
- Verify that all cited sources in the response belong to collections the user can access
- Check that the response content doesn't reference restricted documents

#### Class: `CrossRoleLeakageChecker`

##### Constructor
- Accept `FOLDER_RBAC_MAP` configuration

##### Method: `check(response: str, retrieved_chunks: list[ChunkWithMetadata], user_role: str) → GuardResult`
- **Step 1:** Get the user's accessible collections
- **Step 2:** For each retrieved chunk referenced in the response:
  - Check that `chunk.metadata["collection"]` is in accessible collections
  - Check that `user_role` is in `chunk.metadata["access_roles"]`
- **Step 3:** Scan response text for mentions of document names from restricted collections
  - This catches cases where the LLM might reference documents it shouldn't know about
- If leakage detected → `GuardResult(passed=False, action="block", message="Response contains information from restricted sources")`
- If clean → `GuardResult(passed=True, action="pass")`

##### How Leakage Could Happen
- LLM training data bleeding through (unlikely but possible)
- Prompt injection successfully embedding restricted content
- Bug in retrieval filter allowing restricted chunks through
- LLM reasoning over chunk metadata that references other collections

---

### Guard 3: Source Citation Enforcement

#### Purpose
Ensure every response includes proper source citations so users can verify the information and understand where it came from.

#### Implementation Approach
- Check that the response contains citation markers
- Verify cited sources exist in the retrieved chunks

#### Class: `SourceCitationEnforcer`

##### Constructor
- Define expected citation format (e.g., `[Source: filename, Page: N]`)
- Configure minimum citation count (at least 1 per response, unless it's a clarification)

##### Method: `check(response: str, retrieved_chunks: list[ChunkWithMetadata]) → GuardResult`
- **Step 1:** Parse the response for citation markers
  - Look for patterns like `[Source: ...]`, `[1]`, footnote-style references
- **Step 2:** If no citations found:
  - Check if the response is a clarification question or "I don't know" response (exempt)
  - Otherwise → `GuardResult(passed=False, action="modify")`
  - Auto-append citations based on the retrieved chunks that were used
- **Step 3:** If citations found, verify they match actual retrieved chunks:
  - Check that cited filenames exist in `retrieved_chunks`
  - Check that page numbers are valid
- Return result with citation count and validity in metadata

##### Citation Format Standard
The system should enforce this citation format at the end of responses:

```
**Sources:**
- [document_name.pdf, Page 5] — Section: "Revenue Overview"
- [budget_2026.csv] — Section: "Department Allocations"
```

##### Auto-Citation Injection
If the LLM doesn't include citations, this guard can **inject** them:
- Take the top-k retrieved chunks
- Format them as a "Sources" block
- Append to the response
- Set `action="modify"` with `modified_content` containing the augmented response

---

### Output Guardrail Pipeline

#### Class: `OutputGuardrailPipeline`

##### Constructor
- Accept instances of all 3 output guards
- Define execution order: Cross-Role Leakage → Grounding Check → Source Citation
  - Leakage first (security-critical, fast)
  - Grounding second (quality check)
  - Citation last (can modify the response to add citations)

##### Method: `run(response: str, retrieved_chunks: list[ChunkWithMetadata], user_role: str) → GuardrailPipelineResult`
- Execute guards in order
- **On block:** Stop immediately, return a safe fallback response
- **On flag:** Continue but include the flag in results (UI shows warning)
- **On modify:** Use modified content for subsequent guards
- **On pass:** Continue to next guard
- Return aggregate `GuardrailPipelineResult` with `guardrail_flags` for the UI

---

## Integration with the RAG Pipeline

The guardrails integrate into the main chat endpoint like this:

```
POST /api/chat

1. Authenticate user (JWT)
2. Run InputGuardrailPipeline(query, user_id)
   ├── Rate Limit → pass/block
   ├── Prompt Injection → pass/block
   ├── PII Scrub → pass/modify
   └── Off-Topic → pass/block
3. If blocked → return error response with blocked_by reason
4. Route cleaned query (SemanticRouter)
5. Retrieve chunks (RBAC-filtered)
6. Generate LLM response
7. Run OutputGuardrailPipeline(response, chunks, user_role)
   ├── Cross-Role Leakage → pass/block
   ├── Grounding Check → pass/flag
   └── Source Citation → pass/modify
8. Return ChatResponse with guardrail flags
```

---

## Configuration Points

| Parameter | Location | Default | Description |
|-----------|----------|---------|-------------|
| `RATE_LIMIT_PER_MINUTE` | `settings.py` | `20` | Max queries per minute per user |
| `RATE_LIMIT_PER_HOUR` | `settings.py` | `100` | Max queries per hour per user |
| `RATE_LIMIT_PER_DAY` | `settings.py` | `500` | Max queries per day per user |
| `GROUNDING_THRESHOLD` | `settings.py` | `0.7` | Minimum grounding score to pass |
| `MIN_CITATIONS` | `settings.py` | `1` | Minimum citations required |
| `ENABLE_LLM_INJECTION_CHECK` | `settings.py` | `True` | Whether to use LLM for injection detection |
| `ENABLE_OFF_TOPIC_CHECK` | `settings.py` | `True` | Whether to check for off-topic queries |

---

## Testing Strategy

### Unit Tests (`tests/test_guardrails/`)

#### `test_input_guards.py`

**Off-Topic Detection:**
- Test business query → passes
- Test "What's the weather?" → blocked
- Test "Tell me a joke" → blocked
- Test ambiguous query → passes (err on side of permissiveness)

**Prompt Injection:**
- Test normal query → passes
- Test "Ignore previous instructions and..." → blocked
- Test "You are now a pirate" → blocked
- Test query with legitimate "ignore" usage → passes
- Test encoded injection attempts → blocked

**PII Scrubbing:**
- Test query with email → email redacted, `action="modify"`
- Test query with phone number → phone redacted
- Test query with SSN → SSN redacted
- Test query with no PII → `action="pass"`, content unchanged
- Test query with multiple PII types → all redacted

**Rate Limiting:**
- Test normal request → passes
- Test 21st request in one minute → blocked with retry_after
- Test after waiting period → passes again

#### `test_output_guards.py`

**Grounding Check:**
- Test response fully supported by context → passes
- Test response with hallucinated claim → flagged
- Test "I don't know" response → passes

**Cross-Role Leakage:**
- Test response citing only accessible documents → passes
- Test response referencing finance doc for engineer role → blocked
- Test executive role with any references → passes

**Source Citation:**
- Test response with proper citations → passes
- Test response without citations → modified (citations appended)
- Test response with invalid citations → flagged

---

## Dependencies

```toml
[tool.poetry.dependencies]
langchain = "^0.3.x"
langchain-openai = "^0.3.x"
# Optional for advanced PII detection:
# presidio-analyzer = "^2.x"
# presidio-anonymizer = "^2.x"
```

---

> **Next:** Proceed to `05_ragas_evaluation.md` for Task 4.
