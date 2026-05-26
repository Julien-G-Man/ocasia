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
  "file_text": str | None,
  "user_id": int | None
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

**Current:** Django returns the complete FastAPI response in one HTTP response.
The frontend applies a client-side typewriter animation using `requestAnimationFrame`
(40 chars per frame).

**Planned:** Server-Sent Events per-chunk from FastAPI through Django to the browser.
Deferred to a later sprint.

---

## Tutor Modes

Controlled by `tutor_mode` in the request payload:

- `direct` (default) — answers clearly and concisely.
- `socratic` — guides students through questions. Only reveals the full answer after at
  least two guided exchanges, or if the student explicitly asks for a direct explanation.

A toggle in the UI switches modes. Mode is not persisted server-side.

---

## File Upload

- `POST /api/chat/file/` accepts a file (PDF, DOCX, PPTX, TXT; max 10 MB).
- Text is extracted in Django and forwarded to FastAPI with the message.
- File text is not persisted beyond the request.

---

## Django Endpoints

From `backend/apps/chatbot/urls.py`:

- `POST /api/chat/` — main chat endpoint
- `POST /api/chat/file/` — chat with file attachment
- `GET /api/chat/history/` — load a specific session's messages (`?session_id=`)
- `DELETE /api/chat/history/clear/` — delete a session (`?session_id=`)
- `POST /api/chat/history/rename/` — rename a session
- `GET /api/chatbot/history/` — sidebar session list (newest 10, with `last_message` preview)
- `POST /api/quiz/create-from-agent/` — chatbot-triggered quiz generation (auth required)
