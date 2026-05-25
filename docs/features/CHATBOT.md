# Chatbot Feature

## Frontend

- Page: `src/pages/Chatbot/Chatbot.jsx`
- Sidebar: `src/pages/Chatbot/Sidebar.jsx`
- Route: `/ai-tutor` (`/chatbot` redirects to `/ai-tutor`)

### Sidebar Session UX

- Shows up to the 10 newest saved sessions for authenticated users.
- On load, a new session is created.
- Each session row supports actions via a 3-dot menu:
  - Rename session (in-app modal)
  - Delete session (with confirmation); if the active session is deleted, the next available session loads automatically, or the welcome state is shown if none remain.
- Switching sessions fetches and renders the full message history for the selected session.
- Guests can chat, but session history is not persisted and the empty state prompts signup.

### Request Payload

```json
{
  "message": "string",
  "session_id": "string | null",
  "tutor_mode": "direct | socratic",
  "file_text": "string | null"
}
```

- `search_mode` is removed — the agent decides when to search.
- `tutor_mode` defaults to `"direct"`. A Socratic toggle in the UI sends `"socratic"`.
- `file_text` is pre-extracted by Django before forwarding to FastAPI.

---

## Architecture Overview

```
Browser
  │  POST /api/chat/
  ▼
Django (API Gateway)
  ├── Auth & session management
  ├── Rate limiting & input validation
  ├── Fetch user stats from DB (compact, ~60 tokens)
  ├── Extract file text (if file upload)
  ├── Persist messages to DB (ChatMessage)
  └── Forward to FastAPI
          │  POST /agent/chat
          ▼
       FastAPI (AI Service)
          ├── Minimal system prompt
          ├── Conversation history (forwarded from Django)
          ├── User stats block (forwarded from Django)
          ├── Tool-calling agent loop
          │     ├── kb_search       → retrieve KB chunks on demand
          │     ├── web_search      → Tavily (agent-triggered only)
          │     ├── get_document    → search uploaded file text
          │     └── (quiz_prepare)  → deferred
          └── Return final answer
          │
  Django receives answer
  ├── Persist assistant message to DB
  └── Return to browser (Option C: full response, client typewriter)
```

---

## Guiding Principles

1. **FastAPI owns all AI work.** Tool calling, KB search, web search, system prompt assembly, agent loop — entirely in `ai_service/`.
2. **Django owns all DB work.** Session management, message persistence, user stats, file extraction — entirely in `backend/`.
3. **LLM retrieves context via tools, not prompt injection.** No more 50k-char system prompts. KB content arrives only when the agent calls `kb_search`.
4. **Minimal system prompt.** Role definition + tool behavior rules + tutor mode only. Under 400 tokens.
5. **User stats stay in Django, forwarded to FastAPI.** Avoids HTTP round-trip inside the agent loop. Django fetches from DB and sends with every request.
6. **Three-layer fallback.** Tool error → agent one-shot fallback → FastAPI down (Django static response).

---

## Django Responsibilities

### What Django sends to FastAPI

```python
{
  "message": str,
  "session_id": str | None,
  "tutor_mode": "direct" | "socratic",
  "conversation_history": [...],   # last 10 messages
  "user_stats": {                  # compact DB snapshot, None for guests
    "quizzes_taken": 12,
    "avg_score": 68.0,
    "weak_topics": ["Thermodynamics (38%)", "Cell Biology (55%)"],
    "due_for_review": ["Organic Chemistry"]
  },
  "file_text": str | None,         # extracted by Django, None if no upload
  "user_id": int | None
}
```

### What Django keeps

- Auth, sessions, rate limiting, CORS
- `ChatSession` and `ChatMessage` persistence
- `POST /api/chat/` and `POST /api/chat/file/` endpoints
- Session CRUD: history, rename, delete, clear
- User stats query (`/api/dashboard/stats/` data, 3 cheap DB queries)
- File text extraction (PDF, DOCX, PPTX, TXT)
- Anonymous usage telemetry (24-hour retention)

### What Django removes

- `helpers._build_chatbot_prompt()` — all prompt construction gone
- `helpers._build_agent_context()` — agent context gone
- `text_knowledge_store.py` and `platform_kb/` directory — moved to `ai_service/`
- `prompts.py` — deleted
- `platform_retrieval.py` — deleted
- `CHATBOT_USE_AGENT`, `CHATBOT_RETRIEVAL_*`, `CHATBOT_EMBEDDING_*` settings — removed

---

## FastAPI Responsibilities

### Endpoint

```
POST /agent/chat
```

Accepts the payload Django forwards. Returns `{ "response": str }`.

### Minimal System Prompt

```
You are Lamla, an AI tutor on the Lamla AI learning platform.
You help students understand academic topics, review their progress, and prepare for exams.

You have access to tools:
- kb_search: search the Lamla platform knowledge base. Use this for any question about the platform, its features, pricing, or how things work.
- web_search: search the web. Use this only when the question requires current or external information that is not covered by the knowledge base.
- get_document: search within the student's uploaded file. Use this when the user references their document.

Always try kb_search before web_search for platform-specific questions.
Web search is for academic/factual questions the student asks, not for platform questions.

{tutor_mode_block}
{user_stats_block}
```

`tutor_mode_block` injects the Socratic or direct-answer protocol. `user_stats_block` injects the compact performance snapshot when available. Total: under 400 tokens.

### Tool Catalog

| Tool | Trigger | Returns |
|------|---------|---------|
| `kb_search(query)` | Any platform question | Top-k KB chunks (text) |
| `web_search(query)` | Agent decides (non-platform, factual) | Tavily snippets |
| `get_document(query)` | User references uploaded file | Relevant file passages |
| `quiz_prepare(...)` | *(deferred)* | Navigate action |

### KB Search — Swappable Provider

```
ai_service/kb/
  __init__.py
  base.py          # KBSearchProvider ABC: search(query, top_k) → list[Chunk]
  tfidf_provider.py    # default — token overlap, keyword/heading boost
  openai_provider.py   # toggle-ready — text-embedding-3-small
  loader.py        # loads text_embeddings.json, dispatches to active provider
```

Toggle via `KB_SEARCH_PROVIDER=tfidf|openai` env var. `tfidf` is default — no API cost.

Knowledge base file: `ai_service/platform_kb/text_embeddings.json`.

TF-IDF (Term Frequency-Inverse Document Frequency) is a numerical statistic used in NLP and information retrieval to measure a word's relevance to a document within a larger collection (corpus). It penalizes common filler words by multiplying two metrics:
- TF (Term Frequency): How often a word appears in a document.
- IDF (Inverse Document Frequency): How unique or rare the word is across all documents.


### Three-Layer Fallback

1. **Tool error** — agent catches tool exception, continues with remaining context.
2. **Agent loop failure** — fall back to one-shot LLM call with the message and history only (no tools).
3. **FastAPI unreachable** — Django returns a static apology response; message is not persisted.

---

## Persistence

- Session container: `ChatSession`
- Message rows: `ChatMessage` (ordered by `created_at`)
- Session title: `ChatSession.title`

Authenticated users use explicit `session_id` values to maintain multiple independent conversations.

Anonymous users can chat but history is not persisted across visits.

### Session Retention

- Hard cap: 10 sessions per authenticated user (server-side enforced).
- New session beyond cap → oldest session pruned automatically.
- Dashboard history returns newest 10 sessions only.

### Default Session Naming

On first user message in a new session, the server derives a default title from the first sentence. Users can rename it from the sidebar.

---

## Streaming

**Current (Option C):** Django receives the complete FastAPI response, returns it in one HTTP response. The frontend applies a client-side typewriter animation character-by-character using `requestAnimationFrame`. No SSE, no chunked transfer, no backend changes needed.

**Planned (Option B):** Server-Sent Events with per-chunk streaming from FastAPI through Django to the browser, with tool-progress indicators ("Searching knowledge base…"). Deferred to a later sprint.

---

## Tutor Modes

Controlled by `tutor_mode` in the request payload:

- `direct` (default) — answers clearly and concisely.
- `socratic` — guides students through questions rather than giving direct answers. Follows a strict Socratic protocol: ask what the student knows, build on correct thinking, ask one question at a time, only reveal the full answer after at least two guided exchanges.

A toggle in the frontend UI switches modes per-conversation. Mode is not persisted server-side.

---

## File Upload

- `POST /api/chat/file/` accepts a file, extracts text in Django (PDF, DOCX, PPTX, TXT; max 10 MB, max 50 000 chars).
- Extracted `file_text` is forwarded to FastAPI with the message.
- The agent calls `get_document(query)` to search within the file when relevant.
- File text is not persisted beyond the request.

---

## Django Endpoints

From `backend/apps/chatbot/urls.py`:

- `POST /api/chat/`
- `POST /api/chat/file/`
- `GET /api/chat/history/`
- `DELETE /api/chat/history/clear/`
- `POST /api/chat/history/rename/` (also accepts `PATCH`)
- `GET /api/chatbot/history/` (dashboard/admin history view)

Notes:

- `DELETE /api/chat/history/clear/` supports optional `session_id` for deleting a specific session.
- `GET /api/chat/history/` supports optional `session_id` for loading a specific conversation.
- `/api/chat/stream/` is removed — streaming is handled client-side (Option C).

---

## Implementation Order

1. **FastAPI:** `ai_service/kb/` provider module, move KB files, new `/agent/chat` endpoint, minimal system prompt, tool catalog.
2. **Django:** Simplify `async_views.py` (remove prompt building, add stats fetch + forward), gut `helpers.py`, remove `text_knowledge_store`, remove `prompts.py` and `platform_retrieval.py`, remove dead settings.
3. **Frontend:** Add Socratic mode toggle (sends `tutor_mode`), remove `search_mode` param, add client-side typewriter animation.
4. **Deferred:** `quiz_prepare` tool + frontend action handling. Streaming Option B.
