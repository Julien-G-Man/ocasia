# Agent Implementation — Ocasia

---

## 1. What Agent Means Here

An agent receives a typed list of capabilities (tools), can request to call them instead of
generating a final response, and keeps reasoning over the results until it produces a
definitive answer.

In Ocasia this means:

- The model receives tool definitions (name, description, JSON Schema) at the start of a request.
- The model can return `tool_calls` instead of text.
- The executor runs each tool in-process and returns a `ToolMessage` to the model.
- The loop repeats until the model stops calling tools or `MAX_AGENT_ITERATIONS` is hit.

The tutor agent runs **inside Django**. There is no separate AI service for the tutor.

---

## 2. Architecture

```
React
  │  POST /api/tutor/chat/stream/
  ▼
Django (API + agent runtime)
  ├── Auth, session ownership, and history (TutorConversationStore)
  ├── TutorAgent (apps/tutor/agent/runner.py)
  │     ├── build_tutor_system_prompt(...)
  │     ├── ChatOpenAI.bind_tools(get_tools())
  │     ├── run tools via executor.execute_tool()
  │     └── emit tool_start / tool_done / token / done events
  ├── Persist TutorMessage rows on done
  └── SSE via StreamingHttpResponse
```

Django owns auth, persistence, prompts, tool execution, and the agent loop.

---

## 3. Architectural Boundaries

| Layer | Responsibility |
|---|---|
| Django views (`apps/tutor/views.py`) | Auth, session ownership, history, upload extraction, SSE framing |
| `TutorConversationStore` | Session/message persistence and ownership rules |
| `TutorAgent` | Prompt construction, model calls, tool loop, streaming |
| `registry` / `executor` | Tool schemas, descriptions, per-tool timeouts, error normalization |
| Tool modules | Atomic capabilities (kb_search, generate_quiz, …) |

---

## 4. File Structure

```
backend/apps/tutor/
  agent/
    runner.py            # TutorAgent — run(), stream(), _build_messages(), _run_tool()
    llm.py               # build_chat_model() → ChatOpenAI
    prompts.py           # build_tutor_system_prompt(), wrap_file_context()
    registry.py          # get_tools(), TOOL_DESCRIPTIONS, TOOL_TIMEOUTS, _HANDLERS
    executor.py          # execute_tool() — asyncio.wait_for, never raises
    schemas.py           # TutorAgentResult
    tools/
      content.py         # kb_search, summarize_text, request_quiz_form
      document.py        # search_document
      files.py           # extract_youtube_transcript
      generation.py      # generate_quiz, generate_flashcards, evaluate_answer, explain_concept
      library.py         # list_library_materials
      performance.py     # get_user_performance
      search.py          # search_web
  retrieval/             # RAGEngine, chunking, pgvector search
  knowledge/             # platform KB loader + BM25/vector index
  conversations.py       # TutorConversationStore
  models.py              # TutorSession, TutorMessage, TutorDocument, TutorDocumentChunk
  views.py               # chat, stream, upload, quiz-from-agent, session CRUD
  urls.py
```

---

## 5. Registered Tools

All tools live in `apps/tutor/agent/registry.py` and run in-process.

| Tool | Handler | Purpose | Timeout |
|---|---|---|---|
| `kb_search` | `tools/content.py` | Hybrid KB retrieval | 10s |
| `search_web` | `tools/search.py` | Tavily web search | 12s |
| `search_document` | `tools/document.py` | pgvector study-material retrieval | 15s |
| `extract_youtube_transcript` | `tools/files.py` | YouTube transcript + title | 30s |
| `summarize_text` | `tools/content.py` | Condense long content | 30s |
| `evaluate_answer` | `tools/generation.py` | Grade a free-text answer | 25s |
| `generate_quiz` | `tools/generation.py` | Generate MCQ/short-answer questions | 90s |
| `generate_flashcards` | `tools/generation.py` | Generate flashcards | 45s |
| `explain_concept` | `tools/generation.py` | Focused explanation | 20s |
| `request_quiz_form` | `tools/content.py` | Signal quiz intent (sets `action`/`prefill`) | 5s |
| `get_user_performance` | `tools/performance.py` | Live quiz performance snapshot | 10s |
| `list_library_materials` | `tools/library.py` | Community materials with file links | 10s |

### Input/output schemas

**kb_search**
```
query: str, top_k: int = 4
-> {chunks: [{heading, text, score, source}]}
```

**search_web**
```
query: str, num_results: int = 3
-> {results: [{title, url, snippet}]}
```

**search_document**
```
query: str, top_k: int = 5
-> {chunks: [{text, score, source, page_number}], answer: str}
```

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
study_text: str | None, subject: str,
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

**request_quiz_form**
```
topic: str
-> {status: "quiz_form_shown", topic: str}
```

**get_user_performance**
```
-> {available: bool, total_quizzes: int, avg_score: float,
    all_topics: [[topic, accuracy, count]], recent_quizzes: [...], due_topics: [...]}
```

**list_library_materials**
```
query: str = "", subject: str = "", limit: int = 10
-> {materials: [{id, title, subject, url, filename}], count: int, message: str}
```

---

## 6. Executor

`agent/executor.py` dispatches every tool call and handles all failure modes.
It never raises — errors surface as `{"error": "..."}` dicts.

| Failure | Cause | Handling |
|---|---|---|
| `KeyError` | Unknown tool name | `{"error": "Unknown tool: ..."}` |
| `asyncio.TimeoutError` | Per-tool timeout exceeded | `{"error": "Tool '...' timed out after Ns."}` |
| `ToolExecutionError` | Expected user-facing tool error | `{"error": "..."}` |
| `Exception` | Unexpected failure | `{"error": "Unexpected error: ..."}`, logged with traceback |

`asyncio.wait_for` enforces the per-tool timeout from `registry.TOOL_TIMEOUTS`.

---

## 7. TutorAgent Loop

`TutorAgent` (`agent/runner.py`) is constructed per request.

```python
TutorAgent(
    message=...,
    history=[...],              # [{"role": "user"|"ai", "content": str}]
    tutor_mode="direct",        # or "socratic"
    user_stats=None,            # optional performance snapshot
    file_text=None,             # first upload turn only
    session_id=None,            # injected into search_document
    user_id=None,               # injected into get_user_performance
    has_document=False,
    max_iterations=MAX_AGENT_ITERATIONS,
)
```

### `run()` — buffered

1. `_build_messages()` → `[SystemMessage, *history, HumanMessage]`.
2. `_ensure_model()` → `ChatOpenAI.bind_tools(get_tools())`.
3. `ainvoke` the bound model.
4. If `tool_calls`: append the `AIMessage`, run each tool via `_run_tool`, append
   `ToolMessage`, repeat.
5. If no tool calls: return `TutorAgentResult`.
6. On hitting the iteration cap: force one final answer with "Do not call more tools."

### `stream()` — SSE

Same loop with `astream`, yielding event dicts:

- `{"event": "tool_start", "tool": name, "args": safe_args}`
- `{"event": "tool_done", "tool": name, "duration_ms": int, "result": ...}`
- `{"event": "token", "content": str}`
- `{"event": "done", "side_data": {"tool_calls_made": [...], "action"?, "prefill"?}}`
- `{"event": "error", "message": str}`

### Per-call context injection

`_run_tool` injects request-scoped values before dispatch:

- `search_document` → `tool_args["session_id"] = self.session_id`
- `get_user_performance` → `tool_args["user_id"] = self.user_id`

### Result contract

`TutorAgentResult(response, tool_calls_made, action, prefill)`:

- `action="show_quiz_form"` and `prefill={"topic": ...}` are set when the agent calls
  `request_quiz_form`.
- `tool_calls_made` records every tool name for analytics and debugging.

---

## 8. Django Integration

### Views (`apps/tutor/views.py`)

| View | Endpoint | Purpose |
|---|---|---|
| `TutorChatView` | `POST /api/tutor/chat/` | Non-streaming chat |
| `TutorChatStreamView` | `POST /api/tutor/chat/stream/` | SSE streaming chat |
| `TutorDocumentUploadView` | `POST /api/tutor/upload/` | Upload + first-turn analysis |
| `TutorQuizFromAgentView` | `POST /api/tutor/quiz/from-agent/` | Inline quiz generation |
| `TutorSessionListView` | `GET /api/tutor/sessions/` | Sidebar session list |
| `TutorSessionDetailView` | `GET/PATCH/DELETE /api/tutor/sessions/<id>/` | History, rename, delete |

### Chat flow

1. Parse `message`, `session_id`, `tutor_mode`, and optional `history`.
2. `TutorConversationStore.get_or_create_session(request.user, payload)` — enforces ownership.
3. `history_for_session(...)` — stored messages, or import supplied history.
4. `TutorAgent(**payload).run()` / `.stream()`.
5. `save_turn(session, message, response)` — persist user + AI rows.
6. Return JSON or SSE.

The view injects `user_id` for `get_user_performance` and `session_id` for
`search_document`.

---

## 9. Fallback Strategy

1. **Tool error** — executor catches the exception, returns `{"error": ...}`; the agent
   keeps reasoning.
2. **Iteration cap** — the agent is forced to produce a final answer without more tools.
3. **Unexpected view error** — returns `{"error": "..."}` with HTTP 502; the partial stream
   may already have emitted tokens.

---

## 10. System Prompt

All prompt text lives in `agent/prompts.py`.

`build_tutor_system_prompt(tutor_mode, user_stats)` contains:

- Platform facts (name, URLs, support contacts, feature list)
- Formatting rules (markdown links to platform pages)
- Tool usage rules (kb_search first, search_document for materials, etc.)
- Current date
- User stats block (when available): totals, recent quizzes, weakest topics, due topics
- Socratic mode block (when `tutor_mode == "socratic"`)

`__QUIZ__:` messages in history are summarised to `[Quiz generated: ...]` before being
sent to the model — the raw JSON blob is never forwarded.

---

## 11. What Does NOT Change

| Endpoint | Why it stays direct |
|---|---|
| `POST /api/quiz/generate/` | Explicit generation request |
| `POST /api/flashcards/generate/` | Explicit generation request |
| `POST /api/quiz/submit/` | Deterministic MCQ scoring + persisted session |
| `POST /api/flashcards/review/` | SM-2 algorithm |
| All auth endpoints | Never AI-controlled |
| Materials CRUD | Deterministic |

---

## 12. What the AI Controls vs the Backend

| Decision | Owner |
|---|---|
| Which tool to call and when | AI |
| When to search the KB vs the web vs documents | AI |
| Quiz content, flashcard text | AI |
| Short-answer evaluation | AI |
| Summarization, explanation | AI |
| Authentication | Django |
| MCQ answer comparison | Django (deterministic) |
| SM-2 scheduling | Django (algorithm-based) |
| DB writes (sessions, messages) | Django |
| Input validation | Django |

---

## 13. Key Design Rules

1. **Tools are in-process async functions.** No HTTP round-trips inside the agent.
2. **Tools are stateless.** No DB writes. Django persists everything after the loop returns.
3. **The agent loop has a hard cap.** `MAX_AGENT_ITERATIONS` (default 10).
4. **Schemas drive AI performance.** Tool `description` and input schema are prompt engineering.
5. **Graceful degradation at every level.** Each tool catches its own exceptions; the
   executor never raises; the agent emits an error event.
6. **Prompt text lives in `prompts.py`.** The runner imports functions — it never builds
   strings itself.

---

## 14. Example Trace: YouTube video to flashcards

User: `"Make me flashcards from https://youtube.com/watch?v=abc123"`

```
TutorChatView:
  → get_or_create_session + history_for_session
  → TutorAgent(message=..., history=...).run()

TutorAgent loop:
  iteration 1:
    AI: tool_calls [{name: "extract_youtube_transcript", args: {url: "..."}}]
    executor: {text: "...", title: "Intro to ML", video_id: "abc123"}
  iteration 2:
    AI: tool_calls [{name: "generate_flashcards",
                     args: {text, subject: "Intro to ML", num_cards: 10}}]
    executor: {cards: [{question, answer}, ...]}
  iteration 3:
    AI: text → "Here are 10 flashcards based on Intro to ML: ..."

TutorChatView:
  → save_turn(session, message, response)
  → return {response, session_id}
```

---

## 15. Anti-Patterns to Avoid

- Do not add auth, scoring, or DB writes to any tool.
- Do not build prompt strings in the views — they belong in `prompts.py`.
- Do not let tools call each other. The AI composes them; tools do not.
- Do not call provider SDKs directly from views — go through the agent or `apps.core.ai_engine`.
- Do not remove the direct quiz/flashcard endpoints. The quiz page calls them directly.

---

## 16. Document RAG — Per-Call Session Injection

### Problem

`search_document` needs a `session_id` so it can scope retrieval to the right document.
The global tool registry cannot hold this because `session_id` varies per request.

### Solution

`TutorAgent._run_tool` injects `session_id` into the tool arguments immediately before
dispatch:

```python
if name == "search_document" and self.session_id:
    tool_args["session_id"] = self.session_id
```

This keeps the tool signature explicit while avoiding shared mutable state.

### Upload flow

`TutorDocumentUploadView`:

1. Extracts file text in-process (PDF/DOCX/PPTX/TXT, max 10 MB).
2. Runs `TutorAgent` immediately with `file_text=...` for the first analysis turn.
3. `_maybe_index_upload(...)` (best-effort, fire-and-forget) chunks and embeds the file
   into pgvector.
4. Sets `TutorSession.has_document = True`.

### pgvector details

| Setting | Value |
|---|---|
| Store | PostgreSQL + `pgvector` |
| Embedding model | `text-embedding-3-small` (OpenAI, 1536 dims) |
| Distance metric | Cosine |
| Index | HNSW (`vector_cosine_ops`) |
| Chunking | 800 characters, 120-character overlap |
| Retrieval | Hybrid vector + BM25, reciprocal-rank fusion |
| Scope | Shared corpus; no per-user document permissions yet |

---

## 17. Agentic Quiz Creation — Inline UI Flow

### Two-phase architecture

**Phase 1 — Intent detection and form signal**

1. User expresses quiz intent (e.g., *"Quiz me on Thermodynamics with 10 questions"*).
2. The agent calls `request_quiz_form(topic="Thermodynamics")`.
3. `TutorAgent` sets `action="show_quiz_form"` and `prefill={"topic": "Thermodynamics"}`.
4. The stream's `done` event carries `side_data` with `action` and `prefill`.
5. React renders an inline quiz-parameter card (`QuizFormCard`).

**Phase 2 — Generation and navigation**

6. User confirms or adjusts params and clicks **Generate**.
7. A full-screen loading overlay appears.
8. React POSTs to `POST /api/tutor/quiz/from-agent/` (auth required) with
   `{ topic, num_questions, time_limit, session_id }`.
9. Django fetches `user_stats`, generates the quiz, and saves `__QUIZ__:<json>` as an AI
   message in the current `TutorSession`.
10. React replaces the quiz-parameter card with a **Start Quiz** card.
11. User clicks → `navigate('/quiz/play', { state: { quizData } })`.

### request_quiz_form tool

| Property | Value |
|---|---|
| Name | `request_quiz_form` |
| Type | No-op signal tool |
| Input | `topic: str` |
| Output | `{ "status": "quiz_form_shown", "topic": "<topic>" }` |
| Timeout | 5s |

The handler returns immediately without any LLM call. Its sole purpose is to give the AI a
typed way to signal intent. `TutorAgent` captures the output and sets `action`/`prefill`.

### Quiz card persistence

The Start Quiz card is stored server-side. The sentinel prefix `__QUIZ__:` in
`TutorMessage.content` marks it as quiz data.

- `TutorConversationStore.history_for_session` strips the JSON and replaces it with
  `[Quiz generated: ...]` before forwarding history to the AI.
- `TutorConversationStore.preview_message` renders `"Quiz generated: <subject>"` in the
  sidebar session list.
- `Chatbot.toUiMessage` detects the prefix and returns `{ type: 'start_quiz', quizData }`.

### Frontend message types

| `message.type` | Component | Rendered as |
|---|---|---|
| `"quiz_form"` | `QuizFormCard` | Topic input + num_questions select + time_limit select + Generate button |
| `"start_quiz"` | `StartQuizCard` | Quiz summary line + **Start Quiz** button |

`quiz_form` messages are frontend-only (never persisted).
`start_quiz` messages are reconstructed from `__QUIZ__:` DB messages on every session load.