# AI Tutor Feature

The AI tutor is a Django-native, tool-calling agent. The browser talks only to Django;
the agent loop, prompts, tools, and RAG all run in-process.

## Frontend

- Page: `src/pages/Chatbot/Chatbot.jsx`
- Sidebar: `src/pages/Chatbot/Sidebar.jsx`
- Route: `/ai-tutor` (`/chatbot` redirects to `/ai-tutor`)

### Component Structure

`MessageBubble` is defined **outside** the `Chatbot` component and receives callbacks as
explicit props. Defining it inside caused React to remount it on every re-render (new function
reference = new component type), which reset `QuizFormCard`'s local state between keystrokes.

### Sidebar Session UX

- Shows up to 50 newest sessions for authenticated users (`TutorConversationStore.list_sessions`).
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

`start_quiz` messages are reconstructed from `__QUIZ__:<json>` `TutorMessage` rows on every
session load via `toUiMessage`, so the card persists across sessions and devices.

---

## Architecture

```
Browser
  │  POST /api/tutor/chat/stream/
  ▼
Django (API + agent runtime)
  ├── Auth, session ownership, and history (TutorConversationStore)
  ├── TutorAgent (LangChain loop over langchain_core messages)
  │     ├── bind_tools(get_tools())
  │     ├── per-tool asyncio.wait_for timeouts (executor.py)
  │     └── emits tool_start / tool_done / token / done events
  ├── Persist TutorMessage rows on done
  └── SSE via StreamingHttpResponse
```

---

## Guiding Principles

1. **Django owns AI and data.** The agent loop, prompts, tools, auth, and persistence all
   live in `backend/apps/tutor/`.
2. **LLM retrieves context via tools, not prompt injection.** Knowledge-base and document
   content arrives only when the agent calls `kb_search` or `search_document`.
3. **Minimal system prompt.** Platform facts, formatting, tool guidance, date, and optional
   student stats only.
4. **Per-tool timeouts.** Each tool has its own budget in `registry.TOOL_TIMEOUTS`; a slow
   tool returns a normalized error instead of hanging the turn.
5. **RAG is pgvector-backed.** Document chunks live in PostgreSQL with an HNSW cosine index,
   not an external vector database.

---

## Agent Responsibilities

`TutorAgent` (`apps/tutor/agent/runner.py`) is constructed per request and exposes:

- `run()` — buffered answer, returns `TutorAgentResult`.
- `stream()` — async iterator of SSE event dicts.

### Loop

1. Build `[SystemMessage, *history, HumanMessage]` (`_build_messages`).
2. `ChatOpenAI.bind_tools(get_tools())`.
3. `ainvoke` the model.
4. If the model returns `tool_calls`: append the `AIMessage`, run each tool via
   `_run_tool`, append a `ToolMessage`, repeat (up to `MAX_AGENT_ITERATIONS`).
5. If no tool calls: return the text.
6. On hitting the iteration cap: force one final answer with "do not call more tools".

### Per-call context injection

`_run_tool` injects request-scoped values before dispatch:

- `search_document` receives `session_id`.
- `get_user_performance` receives `user_id`.

### Result contract

`TutorAgentResult(response, tool_calls_made, action, prefill)`:

- `action="show_quiz_form"` and `prefill={"topic": ...}` are set when the agent calls
  `request_quiz_form`.
- `tool_calls_made` records every tool name for analytics and debugging.

---

## Tool Catalog

`registry.get_tools()` builds `StructuredTool` wrappers for:

| Tool | Purpose |
|---|---|
| `kb_search` | Hybrid vector + BM25 search over indexed platform knowledge |
| `search_web` | Current external facts (Tavily; being replaced by hosted web search) |
| `search_document` | Hybrid search over indexed study materials (pgvector) |
| `extract_youtube_transcript` | Fetch transcript and title for a YouTube study video |
| `summarize_text` | Condense long content |
| `generate_quiz` | Generate MCQ/short-answer questions |
| `generate_flashcards` | Generate flashcards |
| `evaluate_answer` | Grade a free-text answer |
| `explain_concept` | Focused explanation of a flashcard/quiz answer |
| `request_quiz_form` | Open the inline quiz form; sets `action`/`prefill` |
| `get_user_performance` | Live quiz performance snapshot for the signed-in student |
| `list_library_materials` | List community study materials with direct file links |

---

## Streaming

**Implemented:** token streaming via Server-Sent Events (SSE) directly from Django.

### Event protocol

| Event type | Payload | Browser action |
|---|---|---|
| `session` | `{session_id}` | Update current session ID, refresh sidebar if new |
| `tool_start` | `{tool}` | Show tool label in thinking bubble |
| `tool_done` | `{tool}` | Clear tool label, return to plain dots |
| `token` | `{content}` | Append text delta to AI bubble in real time; unlock input |
| `done` | `{side_data}` | Finalize message; trigger quiz form if `action=="show_quiz_form"` |
| `error` | `{message}` | Show error text in AI bubble |

### Data flow

```
Browser  POST /api/tutor/chat/stream/  →  Django StreamingHttpResponse
  TutorChatStreamView  →  TutorAgent.stream()
    tool call  → tool_start event
    tool done  → tool_done event
    final text → token events
    complete   → done event with side_data
  Django buffers tokens, saves the full text to TutorMessage on done
Browser appends tokens to the bubble in real time
```

### Tool label display

`TOOL_LABELS` (module-level constant in `Chatbot.jsx`):

| Tool | Label |
|---|---|
| `kb_search` | "Searching knowledge base…" |
| `search_web` | "Searching the web…" |
| `request_quiz_form` | "Preparing quiz…" |
| `search_document` | "Searching your document…" |

File uploads (`POST /api/tutor/upload/`) use the non-streaming endpoint — mixing FormData
with SSE adds complexity for no benefit.

---

## Agentic Quiz Creation

Quizzes can be created inline without leaving the chat.

1. User says "quiz me on X" → agent calls `request_quiz_form(topic="X")`.
2. The agent sets `action="show_quiz_form"`, `prefill={"topic":"X"}`.
3. React renders `QuizFormCard` (topic, num_questions, time_limit).
4. On submit → `POST /api/tutor/quiz/from-agent/` → questions generated → result saved as
   `__QUIZ__:<json>` chat message.
5. `StartQuizCard` appears → click → `/quiz/play`.

The `__QUIZ__:` message persists the quiz card server-side across sessions and devices.
The sidebar preview shows "Quiz generated: Topic" instead of raw JSON.

---

## Persistence

- Session container: `TutorSession` (`apps.tutor.models`).
- Message rows: `TutorMessage` (ordered by `created_at`).
- Session title: derived from the first user message; user can rename via the sidebar.
- Deleting a session also deletes any `TutorDocument` rows scoped to that session.

### Special Message Format

| Prefix | Meaning | Frontend behaviour |
|---|---|---|
| `__QUIZ__:<json>` | Inline quiz generated via the tutor | `toUiMessage` detects prefix → renders `StartQuizCard` |

`__QUIZ__:` blobs are summarised to `[Quiz generated: ...]` before being sent to the model.

---

## Tutor Modes

Controlled by `tutor_mode` in the request payload:

- `direct` (default) — answers clearly and concisely.
- `socratic` — guides students through questions. Only reveals the full answer after at
  least two guided exchanges, or if the student explicitly asks for a direct explanation.

A toggle in the UI switches modes. Mode is not persisted server-side.

---

## File Upload + Document RAG

`POST /api/tutor/upload/` accepts a file (PDF, DOCX, PPTX, TXT; max 10 MB).

### What happens on upload

1. Django extracts text from the file in-process.
2. `TutorAgent` runs immediately with the extracted text as `file_text`, so the first
   response can analyse the document without waiting for indexing.
3. `_maybe_index_upload` (best-effort, fire-and-forget) chunks the file and embeds it into
   pgvector under a `session_id`-scoped source key.
4. `TutorSession.has_document` is set to `True`.

### Subsequent messages in the same session

`TutorAgent` injects `session_id` into `search_document`. When the model decides the
document is relevant, it calls `search_document(query="...")`, which retrieves the top
passages from pgvector with hybrid vector + BM25 ranking.

### Key design choice

The file text is **not** re-sent on every follow-up message. Only query-relevant chunks
are retrieved, keeping context windows small and responses fast.

---

## Endpoints

From `backend/apps/tutor/urls.py`:

- `POST /api/tutor/chat/` — non-streaming chat
- `POST /api/tutor/chat/stream/` — SSE streaming chat (primary browser path)
- `POST /api/tutor/upload/` — chat with a file attachment (non-streaming)
- `POST /api/tutor/quiz/from-agent/` — tutor-triggered quiz generation (auth required)
- `GET /api/tutor/sessions/` — sidebar session list
- `GET /api/tutor/sessions/<session_id>/` — full message history
- `PATCH /api/tutor/sessions/<session_id>/` — rename a session
- `DELETE /api/tutor/sessions/<session_id>/` — delete a session and its documents