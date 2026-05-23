# MCP Implementation — Lamla AI

> **Status:** Core layer implemented and wired. Two functional gaps remain (marked in section 12).

---

## 1. What MCP Means Here

MCP (Model Context Protocol) is a pattern where the AI receives a typed list of capabilities
(tools), can request to call them instead of generating a final response, and continues
reasoning over the results until it produces a definitive answer.

In Lamla this means:
- The AI receives tool definitions (name, description, JSON Schema) at the start of a session.
- The AI can respond with a `tool_use` block instead of text.
- The executor runs the tool in-process and returns the result to the AI.
- The loop repeats until `stop_reason == end_turn` or `max_iterations` is hit.

This is not a different backend. It is an orchestration layer on top of what already exists.

---

## 2. Architecture

### Before MCP

```
React -> Django (auth, validation) -> FastAPI POST /chatbot/ -> one-shot LLM -> Django -> React
```

The AI was a black box at the end of a hardcoded pipeline.

### After MCP

```
React -> Django (auth, validation) -> FastAPI POST /mcp/orchestrate
          |                                     |
     [persist, auth]               [tool registry + executor]
                                             |
                                   [AI <-> tool loop]
                                             |
                                     [final response]
```

The chatbot is now an AI orchestrator. Dedicated quiz and flashcard endpoints are untouched.

---

## 3. Architectural Boundaries (Unchanged)

| Layer | Responsibility | Examples |
|---|---|---|
| Django | Auth, DB, routing, file I/O | Token validation, saving QuizSession, PDF extraction |
| FastAPI | AI execution, tool orchestration | LLM calls, tool registry, MCP executor loop |
| MCP tools | Atomic capabilities | generate_quiz, summarize_text, evaluate_answer |

Django does not know about MCP tools. It calls FastAPI endpoints. FastAPI owns the registry.

---

## 4. File Structure

```
ai_service/
   core/
      ai_client.py          # generate_with_tools() added (4-provider cascade)
   mcp_server/              # new module
      __init__.py
      schemas.py            # ToolDefinition, ToolCall, ToolResult, OrchestratorRequest/Response
      registry.py           # TOOL_REGISTRY (6 tools), get_definitions(), get_handler()
      executor.py           # execute_tool() with 5 error classes + per-tool timeouts
      router.py             # GET /mcp/tools, POST /mcp/call, POST /mcp/orchestrate
      tools/
         __init__.py
         youtube.py         # extract_youtube_transcript()
         evaluate.py        # evaluate_answer() (LLM + string-match fallback)
         summarize.py       # summarize_text() (truncation fallback on AI failure)
   main.py                  # app.include_router(mcp_router, prefix="/mcp") added

backend/apps/chatbot/
   helpers.py               # _build_mcp_context() added (returns system_prompt, messages)
   async_views.py           # chatbot_api_async() branches on CHATBOT_USE_MCP setting
```

Note: the module is named `mcp_server/` (not `mcp/`) to avoid a collision with the `mcp` PyPI
package.

---

## 5. Registered Tools

All tools live in `ai_service/mcp_server/registry.py`.
Handlers run in-process — no internal HTTP round-trips.

| Tool | Handler | Deterministic? | Timeout |
|---|---|---|---|
| `extract_youtube_transcript` | `tools/youtube.py` | Yes (API call) | 30s |
| `summarize_text` | `tools/summarize.py` | No (LLM) | 30s |
| `evaluate_answer` | `tools/evaluate.py` | No (LLM, string-match fallback) | 25s |
| `generate_quiz` | inline in registry.py | No (LLM) | 90s |
| `generate_flashcards` | inline in registry.py | No (LLM) | 45s |
| `explain_concept` | inline in registry.py | No (LLM) | 20s |
| `search_web` | `tools/search.py` | Yes (Tavily API) | 12s |

### Input/output schemas

**extract_youtube_transcript**
```
url: str
-> {text: str, title: str, video_id: str}
```

**summarize_text**
```
text: str, max_words: int = 300, focus: str = ""
-> {summary: str}
```

**evaluate_answer**
```
question: str, correct_answer: str, user_answer: str
-> {is_correct: bool, score: float, reasoning: str}
```

**generate_quiz**
```
study_text: str, subject: str,
difficulty: "easy" | "medium" | "hard" = "medium",
num_mcq: int = 5, num_short: int = 0
-> {mcq_questions: list, short_questions: list, subject: str, difficulty: str}
```

**generate_flashcards**
```
text: str, subject: str, num_cards: int = 10,
difficulty: str = "intermediate", prompt: str = ""
-> {cards: [{question, answer}]}
```

**explain_concept**
```
question: str, answer: str
-> {explanation: str}
```

---

## 6. Executor

`mcp_server/executor.py` dispatches every tool call and handles all failure modes.
It never raises — errors surface through `ToolResult.error`.

| Exception caught | Cause | Log level |
|---|---|---|
| `KeyError` | Unknown tool name | ERROR |
| `asyncio.TimeoutError` | Per-tool timeout exceeded | WARNING |
| `TypeError` | AI passed wrong argument names or types | WARNING |
| `ValueError` | Expected user-facing error (bad URL, transcript unavailable, etc.) | WARNING |
| `Exception` | Unexpected failure | EXCEPTION (full traceback) |

Both sync and async handlers are supported. Sync handlers are wrapped in `asyncio.to_thread()`
automatically.

---

## 7. generate_with_tools() in ai_client.py

New method on `AIClient` alongside the existing `generate_content()`.

```python
async def generate_with_tools(
    self,
    messages: list[dict],   # Anthropic messages format
    tools: list[dict],      # Anthropic-format tool definitions
    max_tokens: int = 1024,
    system: str = "",
    timeout: int = 60,
) -> dict:
    # Returns:
    # {
    #   stop_reason: "tool_use" | "end_turn",
    #   tool_calls:  [{id, name, input}],   # populated when stop_reason == tool_use
    #   text:        str | None,             # populated when stop_reason == end_turn
    #   raw_content: list,                  # content blocks for history reconstruction
    # }
```

**Provider cascade (in order):**
1. Claude — Anthropic SDK native tool use (most reliable)
2. NVIDIA OpenAI-compatible — OpenAI `tools=` format
3. Azure OpenAI — OpenAI `tools=` format
4. Text-mode fallback — embed schemas in system prompt, parse `{"action":"tool_call",...}` JSON

The text-mode fallback works on every provider but is less reliable than native tool use.
It is the last resort, not the default path.

---

## 8. Orchestration Loop

Endpoint: `POST /mcp/orchestrate`  
Auth: `X-Internal-Secret` (same as all other FastAPI endpoints)

```
1. Get tool definitions (all registered, or whitelist from request.tools).
2. Call generate_with_tools(messages, tools, system_prompt).
3. If stop_reason == end_turn  ->  return OrchestratorResponse.
4. If stop_reason == tool_use:
     a. Append assistant message (with tool_use blocks) to messages history.
     b. Execute each tool call via execute_tool().
     c. Append all tool results as a user message.
     d. Go to step 2.
5. If max_iterations reached  ->  return OrchestratorResponse with error field set.
```

**What gets logged:**

| Event | Level |
|---|---|
| Orchestrate start (tools count, max_iterations, messages count) | INFO |
| Each iteration (stop_reason, tool_calls count) | DEBUG |
| Each tool call (name, iteration) | INFO |
| Each tool result (name, output length, duration_ms) | INFO |
| Tool error (name, error message) | WARNING |
| Max iterations hit | WARNING |
| AI provider failure | ERROR |

---

## 9. Django Integration

### chatbot_api_async (apps/chatbot/async_views.py)

The main chatbot endpoint has two paths, selected by a Django setting:

```python
use_mcp = getattr(settings, "CHATBOT_USE_MCP", False)

if use_mcp:
    # Build system_prompt + Anthropic messages list separately
    system_prompt, messages = await _build_mcp_context(user_message, history, user=user)
    resp = await call_fastapi("POST", "/mcp/orchestrate", json={
        "messages": messages,
        "system_prompt": system_prompt,
        "tools": getattr(settings, "CHATBOT_MCP_TOOLS", None),
        "max_tokens": max_tokens,
        "max_iterations": getattr(settings, "CHATBOT_MCP_MAX_ITERATIONS", 5),
    }, timeout=120.0)
    # Falls back to one-shot if orchestrate returns empty or non-200

if not use_mcp:
    # Original path — fully preserved
    full_prompt = await _build_chatbot_prompt(user_message, history, user=user)
    resp = await call_fastapi("POST", "/chatbot/", json={"prompt": full_prompt}, timeout=60.0)
```

Django still handles: session creation, saving ChatMessage records, auth, fallback responses.

### _build_mcp_context (helpers.py)

New helper that returns `(system_prompt: str, messages: list[dict])`.

- `system_prompt` contains platform facts, KB context, persona, and tool-use guidance.
  No conversation history — that goes in messages.
- `messages` is the conversation history in Anthropic `[{role, content}]` format,
  with the current user turn appended as the last entry.

The existing `_build_chatbot_prompt()` is preserved and used as the one-shot fallback.

### Settings

```python
# settings.py or .env
CHATBOT_USE_MCP = True               # Default: False (safe rollout — off until tested)
CHATBOT_MCP_TOOLS = None             # None = all tools. Pass a list to restrict.
CHATBOT_MCP_MAX_ITERATIONS = 5       # Default: 5
CHATBOT_MAX_TOKENS = 1200            # Existing setting, reused for MCP too
```

---

## 10. What Does NOT Change

| Endpoint | Why it stays hardcoded |
|---|---|
| `POST /api/quiz/generate/` | User explicitly requests quiz — no AI reasoning needed |
| `POST /api/flashcards/generate/` | Same — explicit generation request |
| `POST /api/quiz/submit/` | Deterministic MCQ scoring + persisted session |
| `POST /api/flashcards/review/` | SM-2 algorithm |
| All auth endpoints | Never AI-controlled |
| Materials CRUD | Deterministic |
| `POST /api/chat/stream/` | Still one-shot (see Pending) |
| `POST /api/chat/file/` | Still one-shot (see Pending) |

MCP is additive. The original endpoints and the one-shot chatbot path are fully intact.

---

## 11. What the AI Controls vs the Backend

| Decision | Owner |
|---|---|
| Which tool to call and when | AI |
| Quiz content, flashcard text | AI |
| Short-answer evaluation | AI |
| Summarization, explanation | AI |
| Authentication | Django |
| MCQ answer comparison | Django (deterministic string compare) |
| SM-2 scheduling | Django (algorithm-based) |
| DB writes (sessions, decks, messages) | Django |
| Input validation | Django |
| YouTube transcript fetching | Tool handler (deterministic API call, no AI) |

---

## 12. Pending Items

### 12.1 ~~search_web tool~~ — DONE

`mcp_server/tools/search.py` implemented using Tavily (same provider as Django's websearch).
Registered at timeout 12s. The AI now decides when to search rather than a keyword heuristic
in `_build_chatbot_prompt()`. Requires `SEARCH_API_KEY` or `TAVILY_API_KEY` env var.
Falls back to empty results silently if missing.

---

### 12.2 ~~Quiz _evaluate_short_answer~~ — DONE

`apps/quiz/async_views._evaluate_short_answer()` now calls `POST /mcp/call` with
`evaluate_answer` directly instead of routing through `/chatbot/`. Falls back to
string match if the MCP call fails.

---

### 12.3 Stream and file chatbot endpoints

`chatbot_stream_async` (`/api/chat/stream/`) and `chatbot_file_api_async` (`/api/chat/file/`)
still call `POST /chatbot/` directly.

**Stream:** Upgrading requires streaming SSE events for each tool call as well as the final
text — a protocol change. Lower priority.

**File:** The AI could call `summarize_text` first to fit the document in the context window.
Moderate priority.

---

### 12.4 Tests

No unit or integration tests written yet for:
- Individual tool handlers (youtube, evaluate, summarize)
- Executor error handling (timeout, bad arguments, unexpected failure)
- The orchestration loop (tool_use → tool_result → end_turn path)
- Django MCP branch in `chatbot_api_async`

---

## 13. Key Design Rules

1. **Tools are in-process async functions.** No HTTP round-trips inside FastAPI.

2. **Tools are stateless.** No DB writes. Django persists everything after the loop returns.

3. **The orchestrator loop has a hard cap.** Default `max_iterations=5`, max 10.
   If the AI loops unexpectedly, investigate tool descriptions or `system_prompt` — not the cap.

4. **Schemas drive AI performance.** The `description` and `input_schema` of each tool
   directly affect tool selection and argument quality. Treat them like prompt engineering.

5. **Graceful degradation at every level.**
   - Each tool catches its own exceptions and returns `ToolResult.error`.
   - The executor never raises.
   - The orchestrator returns an `error` field instead of crashing.
   - The Django chatbot falls back to one-shot `/chatbot/` if MCP returns empty or fails.

6. **Django never calls `/mcp/tools`.** That endpoint is for debugging and future frontends.
   Django only calls `/mcp/orchestrate` (and `/mcp/call` for direct tool invocation).

---

## 14. Example Trace: YouTube video to flashcards

User: `"Make me flashcards from https://youtube.com/watch?v=abc123"`

```
Django chatbot_api_async:
  - Creates/loads session, saves user message to DB
  - Calls _build_mcp_context() -> (system_prompt, messages)
  - Calls POST /mcp/orchestrate

Orchestrator iteration 1:
  - AI: tool_use { name: "extract_youtube_transcript", input: {url: "..."} }
  - Executor: youtube.py handler -> {text: "...", title: "Intro to ML", video_id: "abc123"}

Orchestrator iteration 2:
  - AI: tool_use { name: "generate_flashcards",
                   input: {text, subject: "Intro to ML", num_cards: 10, difficulty: "medium"} }
  - Executor: registry._generate_flashcards_handler -> {cards: [{question, answer}, ...]}

Orchestrator iteration 3:
  - AI: end_turn { text: "Here are 10 flashcards based on Intro to ML: ..." }
  - Returns OrchestratorResponse(
        response="Here are 10 flashcards...",
        tool_calls_made=["extract_youtube_transcript", "generate_flashcards"],
        iterations=3
    )

Django chatbot_api_async:
  - Saves AI response as ChatMessage
  - Returns JSON to frontend
```

Total: 3 iterations, 2 tool calls. Django handles all persistence.

---

## 15. Anti-Patterns to Avoid

- Do not add auth, scoring, or DB writes to any tool.
- Do not put the MCP layer in Django — it belongs in FastAPI with the AI client.
- Do not let tools call each other. The AI composes them; tools do not.
- Do not expose all tools to every context. Use the `tools` whitelist in `OrchestratorRequest`.
- Do not remove the direct quiz/flashcard endpoints. The quiz page calls them directly.
