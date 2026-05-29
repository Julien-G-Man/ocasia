# Chatbot Feature

## Frontend

- Page: `src/pages/Chatbot/Chatbot.jsx`
- Sidebar: `src/pages/Chatbot/Sidebar.jsx`
- Route: `/ai-tutor` (`/chatbot` redirects to `/ai-tutor`)

### Component Structure

`MessageBubble` is defined **outside** the `Chatbot` component and receives callbacks as
explicit props. Defining it inside caused React to remount it on every re-render (new function
reference = new component type), which reset `QuizFormCard`'s local state between keystrokes.

### Sidebar Session UX

- Shows up to 10 newest sessions for authenticated users.
- Switching sessions fetches and renders the full message history immediately (no confirmation modal).
- Each session row has a 3-dot menu: **Rename** (in-app modal) and **Delete** (confirmation prompt).
  On deleting the active session the next available session loads, or the welcome state shows if none remain.
- The sidebar refreshes automatically after the first message in a new conversation (when the backend
  assigns a real session ID to replace the local `chat-<timestamp>` placeholder).
- Guests can chat; session history is not persisted and the empty state prompts signup.

### Message Types

| `message.type` | Persisted to DB | Rendered as |
|---|---|---|
| `"user"` | Yes | User bubble |
| `"ai"` | Yes | AI bubble with copy button and typewriter animation |
| `"quiz_form"` | **No** (frontend only) | `QuizFormCard` — topic input, num_questions, time_limit selects |
| `"start_quiz"` | Via `__QUIZ__:` prefix in DB | `StartQuizCard` — quiz summary + Start Quiz button |

`start_quiz` messages are reconstructed from `__QUIZ__:<json>` `ChatMessage` rows on every
session load via `toUiMessage`, so the card persists across sessions and devices.

---

## Architecture

```
Browser
  │  POST /api/chat/
  ▼
Django (API Gateway)
  ├── Auth & session management
  ├── Fetch user stats (all topics + last 5 quiz sessions)
  ├── Extract file text (file uploads)
  ├── Persist ChatMessage rows
  └── Forward to FastAPI
          │  POST /agent/chat
          ▼
       FastAPI (AI Service)
          ├── Build system prompt (prompts.py)
          ├── Agent loop — tools: kb_search, search_web, request_quiz_form
          └── Return { "response": str, "action"?: str, "prefill"?: dict }
          │
  Django receives answer
  ├── Persist AI response as ChatMessage
  └── Return { response, session_id, action?, prefill? } to browser
```

---

## Guiding Principles

1. **FastAPI owns all AI work.** Tool calling, KB search, web search, system prompt, agent loop — in `ai_service/`.
2. **Django owns all DB work.** Session management, message persistence, user stats, file extraction — in `backend/`.
3. **LLM retrieves context via tools, not prompt injection.** KB content arrives only when the agent calls `kb_search`.
4. **Minimal system prompt.** Under 400 tokens excluding user stats.
5. **User stats forwarded from Django.** No DB queries inside FastAPI.
6. **Three-layer fallback.** Tool error → agent one-shot → FastAPI down (Django static response).

---

## Django Responsibilities

### What Django sends to FastAPI

```python
{
  "message": str,
  "conversation_history": [...],   # last 20 messages; __QUIZ__: blobs summarised
  "tutor_mode": "direct" | "socratic",
  "user_stats": {
    "total_quizzes": 12,
    "avg_score": 68.0,
    "recent_quizzes": [            # last 5 sessions — lets AI discuss just-taken quizzes
      {"subject": "Thermodynamics", "score": 80.0, "correct": 8, "total": 10},
      ...
    ],
    "all_topics": [                # all TopicPerformance rows, no minimum threshold
      ["Mechanics", 45.0, 10],     # [topic, accuracy%, total_questions]
      ...
    ],
    "due_topics": ["Mechanics"]
  } | None,
  "file_text": str | None,         # only on the first file-upload message
  "user_id": int | None,
  "session_id": str | None,        # used by FastAPI to scope search_document to the right namespace
  "has_document": bool             # True after a file has been indexed for this session
}
```

`all_topics` has no minimum question threshold so topics from a brand-new quiz appear
immediately. Sorted weakest-first so the AI naturally focuses on gaps.

`__QUIZ__:<json>` messages in conversation history are replaced with
`[Quiz generated: Topic, N questions, difficulty]` before forwarding — the raw JSON blob
is never sent to the LLM.

### What Django keeps

- Auth, sessions, CORS
- `ChatSession` and `ChatMessage` persistence
- `POST /api/chat/` and `POST /api/chat/file/` endpoints
- Session CRUD: `GET /api/chat/history/`, `DELETE /api/chat/history/clear/`,
  `POST /api/chat/history/rename/`, `GET /api/chatbot/history/`
- User stats query (4 cheap DB queries)
- File text extraction (PDF, DOCX, PPTX, TXT)

---

## FastAPI Responsibilities

### Endpoint

```
POST /agent/chat
```

Returns `{ "response": str }`, optionally with `"action"` and `"prefill"` for quiz form signalling.

### System Prompt

Built by `build_chat_system_prompt(tutor_mode, user_stats)` in `agent/prompts.py`.
The router never constructs strings. Sections:

- Platform facts (name, URLs, support contacts, feature list)
- Formatting rules (markdown links to platform pages)
- Tool usage rules
- Current date
- User stats block (when available)
- Socratic mode block (when `tutor_mode == "socratic"`)

### Tool Catalog (chatbot subset)

`_CHAT_TOOLS = ["kb_search", "search_web", "request_quiz_form"]`

| Tool | Trigger | Returns |
|---|---|---|
| `kb_search(query)` | Any platform question | Top-k KB chunks |
| `search_web(query)` | Agent decides — non-platform factual questions | Tavily snippets |
| `request_quiz_form(topic)` | User expresses quiz intent | `{status, topic}` (no-op; router sets `action`) |

### Three-Layer Fallback

1. **Tool error** — executor catches exception, agent continues reasoning.
2. **Agent loop failure** — one-shot `generate_content()` call (no tools, system + message only).
3. **FastAPI unreachable** — Django returns a static keyword-matched response; message not persisted.

---

## Agentic Quiz Creation

Quizzes can be created inline without leaving the chat. Full flow documented in
[AGENT_IMPLEMENTATION.md § 17](../architecture-design/AGENT_IMPLEMENTATION.md).

**Short version:**

1. User says "quiz me on X" → agent calls `request_quiz_form(topic="X")`.
2. Router sets `action="show_quiz_form"`, `prefill={"topic":"X"}` in the response.
3. React renders `QuizFormCard` (topic, num_questions, time_limit).
4. A full-screen loading overlay appears while the quiz generates (matches CreateQuiz page style).
5. On submit → `POST /api/quiz/create-from-agent/` → FastAPI determines difficulty from user stats
   → questions generated → result saved as `__QUIZ__:<json>` chat message.
6. `StartQuizCard` appears → click → `/quiz/play`.

The `__QUIZ__:` message persists the quiz card server-side across sessions and devices.
The sidebar preview shows "Quiz generated: Topic" instead of raw JSON.

---

## Persistence

- Session container: `ChatSession`
- Message rows: `ChatMessage` (ordered by `created_at`)
- Session title: derived from first user message; user can rename via sidebar.

### Special Message Format

| Prefix | Meaning | Frontend behaviour |
|---|---|---|
| `__QUIZ__:<json>` | Inline quiz generated via chatbot | `toUiMessage` detects prefix → renders `StartQuizCard` |

### Session Retention

- Hard cap: 10 sessions per authenticated user (server-side enforced on creation).
- Dashboard history returns newest 10 sessions only.

---

## Streaming

**Implemented:** Real token streaming via Server-Sent Events (SSE).

### Event protocol

| Event type | Payload | Browser action |
|---|---|---|
| `session` | `{session_id}` | Update current session ID, refresh sidebar if new |
| `tool_start` | `{tool}` | Show tool label in thinking bubble ("Searching knowledge base…") |
| `tool_done` | `{tool}` | Clear tool label, return to plain dots |
| `token` | `{content}` | Append text delta to AI bubble in real time; unlock input |
| `done` | `{side_data}` | Finalize message; trigger quiz form if `action=="show_quiz_form"` |
| `error` | `{message}` | Show error text in AI bubble |

### Data flow

```
Browser  POST /api/chat/stream/  →  Django StreamingHttpResponse
  Django  POST /agent/chat/stream  →  FastAPI StreamingResponse
    FastAPI  _run_agent_loop_stream()
      Tool calls: Claude streams tool_use block → tool_start event
      Tool execution: execute_tool() → tool_done event
      Final response: Claude streams text_delta → token events
      Complete: done event with side_data
  Django buffers tokens, saves full text to DB on done
Browser appends tokens to bubble in real time
```

### Why SSE through Django

Django owns auth and DB. FastAPI owns AI. The browser cannot call FastAPI directly
(internal-only). Django proxies the SSE stream with `httpx.AsyncClient.stream()` and
forwards events verbatim using `StreamingHttpResponse`.

### Tool label display

When the model calls a tool, `tool_start` updates the thinking bubble with a
human-readable label. `TOOL_LABELS` (module-level constant in `Chatbot.jsx`):

| Tool | Label |
|---|---|
| `kb_search` | "Searching knowledge base…" |
| `search_web` | "Searching the web…" |
| `request_quiz_form` | "Preparing quiz…" |
| `search_document` | "Searching your document…" |

### Fallback

File uploads (`POST /api/chat/file/`) still use the non-streaming endpoint
(`POST /agent/chat`) — mixing FormData with SSE adds complexity for no benefit.
The non-streaming path also remains available as an internal fallback.

---

## Tutor Modes

Controlled by `tutor_mode` in the request payload:

- `direct` (default) — answers clearly and concisely.
- `socratic` — guides students through questions. Only reveals the full answer after at
  least two guided exchanges, or if the student explicitly asks for a direct explanation.

A toggle in the UI switches modes. Mode is not persisted server-side.

---

## File Upload + Document RAG

`POST /api/chat/file/` accepts a file (PDF, DOCX, PPTX, TXT; max 10 MB).

### What happens on upload

1. Django extracts text from the file in-process.
2. Text is chunked into 500-word overlapping segments (`chunk_text`, overlap=100).
3. A background task POSTs chunks to `POST /agent/document/index` (FastAPI) — runs
   concurrently while Django processes the first message. FastAPI embeds all chunks
   with `text-embedding-3-small` and stores them in Upstash Vector under
   `namespace=session_id`.
4. `ChatSession.has_document` is set to `True`.
5. The full extracted text is still forwarded to FastAPI for the **first** AI response
   (so the AI can give an immediate summary/analysis without waiting for indexing).

### Subsequent messages in the same session

Every follow-up message includes `has_document=True` and `session_id` in the FastAPI
payload. FastAPI injects the `search_document` tool into the agent loop. When the AI
decides the document is relevant, it calls `search_document(query="...")` which embeds
the query and retrieves the top-5 most similar chunks from Upstash Vector.

The user sees **"Searching your document…"** in the thinking bubble while this runs.

### Key design choice

The file text is **not** re-sent on every follow-up message. Only the query-relevant
chunks are retrieved, keeping context windows small and responses fast.

---

## Django Endpoints

From `backend/apps/chatbot/urls.py`:

- `POST /api/chat/` — non-streaming chat (kept for internal fallback; file path still uses this)
- `POST /api/chat/stream/` — SSE streaming chat (primary browser path)
- `POST /api/chat/file/` — chat with file attachment (non-streaming)
- `GET /api/chat/history/` — load a specific session's messages (`?session_id=`)
- `DELETE /api/chat/history/clear/` — delete a session (`?session_id=`)
- `POST /api/chat/history/rename/` — rename a session
- `GET /api/chatbot/history/` — sidebar session list (newest 10, with `last_message` preview)
- `POST /api/quiz/create-from-agent/` — chatbot-triggered quiz generation (auth required)
