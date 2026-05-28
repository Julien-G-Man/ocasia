# Agent Implementation — Lamla AI

---

## 1. What Agent Means Here

Agent is a pattern where the AI receives a typed list of capabilities (tools), can request
to call them instead of generating a final response, and continues reasoning over the results
until it produces a definitive answer.

In Lamla this means:
- The AI receives tool definitions (name, description, JSON Schema) at the start of a request.
- The AI can respond with a `tool_use` block instead of text.
- The executor runs the tool in-process and returns the result to the AI.
- The loop repeats until `stop_reason == end_turn` or `max_iterations` is hit.

---
## 2. Architecture

```
React
  │  POST /api/chat/
  ▼
Django (API Gateway)
  ├── Auth & session management
  ├── Fetch user stats from DB (compact, ~60 tokens)
  ├── Extract file text (file uploads)
  ├── Persist messages (ChatMessage)
  └── Forward to FastAPI
          │  POST /agent/chat
          ▼
       FastAPI (AI Service)
          ├── Build minimal system prompt (prompts.py)
          ├── Run agent loop (router.py)
          │     ├── kb_search  → ai_service/kb/ provider
          │     └── web_search → Tavily
          └── Return { "response": str }
```

Django owns all DB work. FastAPI owns all AI work. No prompt construction in Django.

---

## 3. Architectural Boundaries

| Layer | Responsibility |
|---|---|
| Django | Auth, session/message persistence, user stats, file extraction |
| FastAPI | System prompt, agent loop, tool orchestration, LLM calls |
| Agent tools | Atomic capabilities (kb_search, web_search, generate_quiz, …) |

Django never builds prompts. FastAPI never writes to the DB.

---

## 4. File Structure

```
ai_service/
  core/
    ai_client.py         # generate_content() + generate_with_tools()
  agent/
    prompts.py           # All system prompt construction (build_chat_system_prompt, etc.)
    schemas.py           # ToolDefinition, ToolCall, ToolResult, OrchestratorRequest/Response, ChatRequest
    registry.py          # TOOL_REGISTRY, get_definitions(), get_handler()
    executor.py          # execute_tool() — 5 error classes, per-tool timeouts, never raises
    router.py            # Route handlers only: /tools, /call, /orchestrate, /chat
    tools/
      youtube.py         # extract_youtube_transcript()
      evaluate.py        # evaluate_answer()
      summarize.py       # summarize_text()
      search.py          # search_web() via Tavily
  kb_config/
    base.py              # KBSearchProvider ABC
    tfidf_provider.py    # Default — token overlap + keyword/heading boost
    loader.py            # Resolves platform_kb/ path, instantiates provider, exposes kb_store singleton
    md_parser.py         # Loads kb_index.json + .md files, merges into chunk dicts
  platform_kb/
    kb_index.json        # Chunk index: chunk_id -> {heading, source_file, keywords}
    *.md                 # Content files, one ## section per chunk, matched by heading
  services/
    quiz/                # POST /quiz/ — standalone quiz generation
    flashcards/          # POST /flashcards/ — standalone flashcard generation

backend/apps/chatbot/
  async_views.py         # Proxy views: fetch stats, forward to /agent/chat, persist response
  helpers.py             # Session/auth/DB helpers and _fetch_user_performance_sync()
```

---

## 5. Registered Tools

All tools live in `ai_service/agent/registry.py`.
Handlers run in-process — no internal HTTP round-trips.

| Tool | Handler | Notes | Timeout |
|---|---|---|---|
| `kb_search` | `kb/loader.py` singleton | Platform knowledge retrieval | 5s |
| `search_web` | `tools/search.py` | Tavily — agent decides when to call | 12s |
| `extract_youtube_transcript` | `tools/youtube.py` | Deterministic API call | 30s |
| `summarize_text` | `tools/summarize.py` | LLM — truncation fallback on failure | 30s |
| `evaluate_answer` | `tools/evaluate.py` | LLM + string-match fallback | 25s |
| `generate_quiz` | inline in registry.py | LLM via quiz service | 90s |
| `generate_flashcards` | inline in registry.py | LLM via flashcards service | 45s |
| `explain_concept` | inline in registry.py | LLM | 20s |

### Chatbot tool subset

`POST /agent/chat` exposes exactly these three tools (`_CHAT_TOOLS`):

```python
_CHAT_TOOLS = ["kb_search", "search_web", "request_quiz_form"]
```

All other tools (YouTube, summarize, evaluate, generate_quiz, generate_flashcards, explain_concept)
are available via `POST /agent/orchestrate` when called with the appropriate whitelist.

### Input/output schemas

**kb_search**
```
query: str, top_k: int = 4
-> {chunks: [{heading, text}]}
```

**search_web**
```
query: str, num_results: int = 3
-> {results: [{title, url, snippet}]}
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

`agent/executor.py` dispatches every tool call and handles all failure modes.
It never raises — errors surface through `ToolResult.error`.

| Exception caught | Cause | Log level |
|---|---|---|
| `KeyError` | Unknown tool name | ERROR |
| `asyncio.TimeoutError` | Per-tool timeout exceeded | WARNING |
| `TypeError` | AI passed wrong argument names or types | WARNING |
| `ValueError` | Expected user-facing error (bad URL, transcript unavailable, etc.) | WARNING |
| `Exception` | Unexpected failure | EXCEPTION (full traceback) |

Both sync and async handlers are supported. Sync handlers are wrapped in `asyncio.to_thread()`.

---

## 7. generate_with_tools() in ai_client.py

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

---

## 8. Agent Endpoints

### POST /agent/chat — Primary chatbot endpoint

Accepts the structured payload from Django. Builds the system prompt internally, runs the
agent loop restricted to `kb_search` + `web_search`, falls back to one-shot on failure.

```json
{
  "message": "string",
  "conversation_history": [...],
  "tutor_mode": "direct | socratic",
  "user_stats": { ... } | null,
  "file_text": "string" | null,
  "user_id": int | null
}
```

Returns `{ "response": str }`.

### POST /agent/orchestrate — Generic tool-loop endpoint

Used by quiz evaluation and other non-chatbot flows that need tool access.
Accepts `messages`, `tools` whitelist, `system_prompt`, `max_tokens`, `max_iterations`.
Returns `OrchestratorResponse`.

### GET /agent/tools, POST /agent/call

Debug/direct-call endpoints. Not called by Django in production.

---

## 9. Django Integration

`async_views.chatbot_api_async` flow:

1. Parse `message`, `session_id`, `tutor_mode` from request body.
2. Resolve auth + get/create session.
3. Save user message to DB.
4. Fetch last 20 messages from session history.
5. Fetch user stats via `_fetch_user_performance_sync()` — all topics (no minimum threshold), last 5 quiz sessions, and due topics.
6. `POST /agent/chat` with the structured payload.
7. On FastAPI failure: return static fallback (message not persisted).
8. Save AI response to DB, return to React.

There is no agent flag, no prompt building, no one-shot path in Django.
FastAPI owns the full AI decision tree.

---

## 10. Fallback Strategy (Three Layers)

1. **Tool error** — executor catches exception, returns `ToolResult.error`; agent continues reasoning.
2. **Agent loop empty/failed** — one-shot `generate_content()` call in `router.py` (no tools, just system + message).
3. **FastAPI unreachable** — Django returns a static keyword-matched response; message is not persisted.

---

## 11. System Prompt

All prompt text lives in `ai_service/agent/prompts.py`. The router never builds strings.

The chatbot system prompt (`build_chat_system_prompt`) contains:
- Platform facts (name, URLs, support contacts)
- Formatting rules (markdown links for page references)
- Tool usage rules (kb_search first, web_search for external only, request_quiz_form for quiz intent)
- Current date
- User stats block (injected if available): recent quiz sessions, all topics sorted weakest-first, due topics
- Socratic mode block (injected if `tutor_mode == "socratic"`)

The user stats block format (from `_fetch_user_performance_sync`):
```
STUDENT LEARNING PROGRESS:
[5 quizzes taken | Avg score: 72.4%]
Recent quizzes: Thermodynamics (8/10, 80%), Mechanics (4/10, 40%)
All topics (weakest first): Mechanics (40%, 10q), Calculus (58%, 6q), Thermodynamics (80%, 10q)
Due for review: Mechanics
```

`__QUIZ__:` messages in conversation history are summarized to `[Quiz generated: Topic, N questions, difficulty]`
before being sent to the AI — the raw JSON blob is never forwarded.

---

## 12. What Does NOT Change

| Endpoint | Why it stays hardcoded |
|---|---|
| `POST /api/quiz/generate/` | User explicitly requests quiz — no AI reasoning needed |
| `POST /api/flashcards/generate/` | Same — explicit generation request |
| `POST /api/quiz/submit/` | Deterministic MCQ scoring + persisted session |
| `POST /api/flashcards/review/` | SM-2 algorithm |
| All auth endpoints | Never AI-controlled |
| Materials CRUD | Deterministic |

---

## 13. What the AI Controls vs the Backend

| Decision | Owner |
|---|---|
| Which tool to call and when | AI |
| When to search the KB vs the web | AI |
| Quiz content, flashcard text | AI |
| Short-answer evaluation | AI |
| Summarization, explanation | AI |
| Authentication | Django |
| MCQ answer comparison | Django (deterministic) |
| SM-2 scheduling | Django (algorithm-based) |
| DB writes (sessions, decks, messages) | Django |
| Input validation | Django |

---

## 14. Key Design Rules

1. **Tools are in-process async functions.** No HTTP round-trips inside FastAPI.
2. **Tools are stateless.** No DB writes. Django persists everything after the loop returns.
3. **The agent loop has a hard cap.** Default `max_iterations=5`, max 10.
4. **Schemas drive AI performance.** Tool `description` and `input_schema` are prompt engineering.
5. **Graceful degradation at every level.** Each tool catches its own exceptions; the executor never raises; the router returns an error field; Django has a static fallback.
6. **Prompt text lives in `prompts.py`.** The router imports functions — it never builds strings itself.

---

## 15. Example Trace: YouTube video to flashcards

User: `"Make me flashcards from https://youtube.com/watch?v=abc123"`

```
Django chatbot_api_async:
  → Creates/loads session, saves user message to DB
  → Fetches user stats
  → POST /agent/chat { message, conversation_history, user_stats, tutor_mode: "direct" }

FastAPI /agent/chat:
  → Builds system prompt
  → Agent loop iteration 1:
      AI: tool_use { name: "extract_youtube_transcript", input: {url: "..."} }
      Executor: {text: "...", title: "Intro to ML", video_id: "abc123"}
  → Agent loop iteration 2:
      AI: tool_use { name: "generate_flashcards",
                     input: {text, subject: "Intro to ML", num_cards: 10} }
      Executor: {cards: [{question, answer}, ...]}
  → Agent loop iteration 3:
      AI: end_turn { text: "Here are 10 flashcards based on Intro to ML: ..." }
  → Returns { "response": "Here are 10 flashcards..." }

Django chatbot_api_async:
  → Saves AI response as ChatMessage
  → Returns JSON to React
```

---

## 16. Anti-Patterns to Avoid

- Do not add auth, scoring, or DB writes to any tool.
- Do not put prompt construction in Django — it belongs in FastAPI `prompts.py`.
- Do not let tools call each other. The AI composes them; tools do not.
- Do not expose all tools to the chatbot. Use `_CHAT_TOOLS = ["kb_search", "web_search", "request_quiz_form"]`.
- Do not remove the direct quiz/flashcard endpoints. The quiz page calls them directly.

---

## 17. Agentic Quiz Creation — Inline UI Flow

### Problem solved

The previous approach required the chatbot to fill a text box on the Create Quiz page, which
triggered a second unrelated LLM call. This design makes the chatbot the single entry point for
quiz creation — no navigation away, no second agent call.

### Two-phase architecture

**Phase 1 — Intent detection and form signal**

1. User expresses quiz intent (e.g., *"Quiz me on Thermodynamics with 10 questions"*).
2. The agent calls `request_quiz_form(topic="Thermodynamics")` — a no-op tool that returns immediately.
3. `_run_agent_loop` detects this call and sets `side_data["action"] = "show_quiz_form"`.
4. `/agent/chat` returns `{ "response": "...", "action": "show_quiz_form", "prefill": {"topic": "Thermodynamics"} }`.
5. Django passes `action` and `prefill` through to React.
6. React appends an inline quiz-param card to the chat history (topic, num_questions, time_limit inputs, pre-filled from `prefill`).

**Phase 2 — Generation and navigation**

7. User confirms or adjusts params and clicks **Generate**.
8. A full-screen loading overlay (spinner + "Generating your quiz with AI…") appears, matching the quiz/flashcard creation page style.
9. React POSTs to `POST /api/quiz/create-from-agent/` (Django proxy — requires auth) with `{ topic, num_questions, time_limit, session_id }`.
10. Django fetches `user_stats`, proxies to `POST /agent/quiz/generate/` (FastAPI), then saves `__QUIZ__:<json>` as an AI message in the current `ChatSession`.
11. FastAPI auto-determines difficulty from `user_stats` and calls `_generate_quiz_handler`.
12. Returns `{ "quiz_data": { mcq_questions, short_questions, subject, difficulty, id, time_limit } }`.
13. Overlay disappears. React replaces the quiz-param card with a **Start Quiz** card.
14. User clicks → `navigate('/quiz/play', { state: { quizData } })`. No second AI call.

```
React
  │  user: "quiz me on Thermodynamics"
  ▼
Django POST /api/chat/
  └── POST /agent/chat (FastAPI)
        agent loop → request_quiz_form("Thermodynamics")
        side_data = { action: "show_quiz_form", prefill: { topic: "Thermodynamics" } }
        return { response: "...", action: "show_quiz_form", prefill: {...} }
  └── passes action + prefill through to React

React renders inline quiz-param card
  │  user fills form, clicks Generate
  ▼
Django POST /api/quiz/create-from-agent/
  └── fetches user_stats
  └── POST /agent/quiz/generate/ (FastAPI)
        _determine_difficulty(user_stats, topic)
        _generate_quiz_handler(study_text=..., subject=topic, ...)
        return { quiz_data: { mcq_questions, ..., id, time_limit } }
  └── returns quiz_data to React

React renders Start Quiz card → navigate('/quiz/play')
```

### request_quiz_form tool

| Property | Value |
|---|---|
| Name | `request_quiz_form` |
| Type | No-op signal tool |
| Input | `topic: str` (optional, extracted from conversation) |
| Output | `{ "status": "quiz_form_shown", "topic": "<topic>" }` |
| Timeout | 2s |

The handler returns immediately without any LLM call. Its sole purpose is to give the AI a
typed way to signal intent. The router captures the output and sets `side_data`, which flows
out-of-band through the response.

### Difficulty auto-determination

`POST /agent/quiz/generate/` computes difficulty from `user_stats` without asking the user.
It looks up the specific topic in `all_topics` first, then falls back to overall average:

| Condition (evaluated in order) | Difficulty |
|---|---|
| `user_stats` absent or empty | medium |
| Topic found in `all_topics`, accuracy < 60% | hard (struggling — extra practice) |
| Topic found in `all_topics`, accuracy 60–79% | medium |
| Topic found in `all_topics`, accuracy ≥ 80% | hard (already strong — challenge further) |
| Topic not found, `avg_score` ≥ 80% | hard |
| Topic not found, `avg_score` 60–79% | medium |
| Topic not found, `avg_score` < 60% | easy |

### _run_agent_loop signature change

`_run_agent_loop` now returns a **3-tuple** `(text, error, side_data)`.
`side_data` carries out-of-band signals from tool execution.
The chatbot route unpacks this and merges it into the HTTP response.
Callers that only needed the 2-tuple were internal — there is one call site in the router.

### New FastAPI endpoint

`POST /agent/quiz/generate/` — standalone, not part of the conversational loop.

```json
Request:
{
  "topic": "string",
  "num_questions": 10,
  "time_limit": 15,
  "user_stats": { ... } | null
}

Response:
{
  "quiz_data": {
    "mcq_questions": [...],
    "short_questions": [...],
    "subject": "string",
    "difficulty": "easy|medium|hard",
    "id": "agent-<hex8>",
    "time_limit": 15
  }
}
```

### Django proxy

`POST /api/quiz/create-from-agent/` — authenticated view that:
1. Reads `topic`, `num_questions`, `time_limit`, and `session_id` from the request body.
2. Authenticates the user via `_resolve_authenticated_user` (does **not** create a session).
3. Fetches `user_stats` for the logged-in user.
4. Proxies to FastAPI `/agent/quiz/generate/`.
5. On success, looks up the existing `ChatSession` by `session_id` and saves `__QUIZ__:<json>` as an AI message — this is what makes the Start Quiz card persist across sessions and devices.
6. Returns `{ "quiz_data": ... }` to the frontend.

No `QuizSession` is created here — Django creates one only when the user submits answers
via `POST /api/quiz/submit/`, exactly as with manually created quizzes.

### Quiz card persistence

The Start Quiz card is stored server-side, not in localStorage. The sentinel prefix `__QUIZ__:`
in the `ChatMessage.content` field marks it as quiz data.

- **`_get_conversation_history`** strips the JSON and replaces it with
  `[Quiz generated: Topic, N questions, difficulty]` before forwarding history to the AI.
- **`dashboard_views._preview`** renders `"Quiz generated: Topic"` in the sidebar session list.
- **`Chatbot.toUiMessage`** detects the prefix and returns `{ type: 'start_quiz', quizData }`,
  which renders `StartQuizCard` — this runs automatically on every session load, across any browser or device.

### Frontend message types

| `message.type` | Component | Rendered as |
|---|---|---|
| `"quiz_form"` | `QuizFormCard` | Topic input + num_questions select + time_limit select + Generate button |
| `"start_quiz"` | `StartQuizCard` | Quiz summary line + **Start Quiz** button |

Both are rendered inside the standard AI bubble area to stay visually consistent.
`QuizFormCard` maintains its own local state (topic, numQ, timeLimit) and is pre-filled
from `message.prefillTopic` when the agent extracted the topic from the conversation.

`quiz_form` messages are frontend-only (never persisted to DB).
`start_quiz` messages are reconstructed from `__QUIZ__:` DB messages on every session load via `toUiMessage`.

### Component structure

`MessageBubble` is defined **outside** the `Chatbot` component and receives all callbacks as
explicit props (`onCopy`, `onQuizGenerate`, `quizFormGenerating`, `onStartQuiz`, `copiedId`).
Defining it inside `Chatbot` caused React to remount it on every re-render (new function
reference = new component type), which reset `QuizFormCard`'s local topic input.
