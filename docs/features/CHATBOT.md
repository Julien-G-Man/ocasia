# Chatbot Feature

## Frontend

- Page: `src/pages/Chatbot/Chatbot.jsx`
- Sidebar: `src/pages/Chatbot/Sidebar.jsx`
- Route: `/ai-tutor` (`/chatbot` redirects to `/ai-tutor`)

### Sidebar Session UX (Current)

- Shows up to the 10 newest saved sessions for authenticated users.
- On load, the most recent session is automatically selected and its full message history is fetched and rendered.
- Each session row supports actions via a 3-dot menu:
	- Rename session (in-app modal)
	- Delete session (with confirmation); if the active session is deleted, the next available session loads automatically, or the welcome state is shown if none remain.
- Switching sessions fetches and renders the full message history for the selected session.
- Guests can chat, but session history is not persisted and the empty state prompts signup.

## Django Endpoints

From `backend/apps/chatbot/urls.py`:

- `POST /api/chat/`
- `POST /api/chat/stream/`
- `POST /api/chat/file/`
- `GET /api/chat/history/`
- `DELETE /api/chat/history/clear/`
- `POST /api/chat/history/rename/` (also accepts `PATCH`)
- `GET /api/chatbot/history/` (dashboard/admin history view)

Notes:

- `DELETE /api/chat/history/clear/` supports optional `session_id` for deleting a specific session.
- `GET /api/chat/history/` supports optional `session_id` for loading a specific conversation.

## FastAPI Endpoint

- Internal worker route: `POST /chatbot/`

## Persistence

- Session container: `ChatSession`
- Message rows: `ChatMessage` (ordered by created_at)
- Session title: `ChatSession.title`

Authenticated users use explicit `session_id` values so one user can maintain multiple independent conversations.

Anonymous users can chat but session history is not persisted across visits.

Operational telemetry for anonymous API usage is retained for 24 hours for admin monitoring. This includes request metadata and, for non-stream chat requests, the latest user message and tutor response in the admin anonymous-usage dashboard feed.

Session retention policy:

- A hard cap of 10 sessions per authenticated user is enforced server-side.
- When a new session is created beyond the cap, older sessions are pruned automatically.
- Dashboard history responses also return only the newest 10 sessions.

Default session naming:

- On first user message in a new session, the server derives a default title from the first sentence.
- Users can later rename that title from the sidebar.

Performance notes:

- Dashboard session listing avoids N+1 queries by annotating message count and latest message.
- Chat models include indexes for user/session recency and session message retrieval.
- History endpoints emit duration logs for lightweight latency monitoring.

## Prompt Construction

`helpers._build_chatbot_prompt()` assembles the full system prompt in this order:

1. **Static core facts block** — hardcoded platform name, full URLs (`https://lamla-ai.vercel.app/...`), feature list, support contacts. Always present regardless of retrieval.
2. **Full platform knowledge base** — all content from `text_embeddings.json` via `TextKnowledgeStore.get_all_context()`. Every chunk is injected every time so the AI never has to guess platform details.
3. **Document context** — extracted file text (file upload flow only), wrapped in a clear boundary so the AI treats it as source material, not instructions.
4. **User context** — authenticated username if available.
5. **User learning progress** — compact performance snapshot for authenticated users who have quiz history (see below). Absent for guests and users with no quiz history.
6. **Current date/time.**
7. **Conversation history** — last 10 messages from the session.
8. **Student question.**

### User Learning Progress Injection

For every authenticated user who has taken at least one quiz, a compact block is injected into the system prompt at message-build time — no round trip, no tool call:

```
Student learning progress:
[12 quizzes taken | Avg score: 68.0%]
Weak topics: Thermodynamics (38.0%), Cell Biology (55.0%)
Due for review: Organic Chemistry
```

This is ~60 tokens. The bot uses it when relevant (e.g. "what should I study?", "how am I doing?") and ignores it when the question is unrelated. It is never injected for guests or users with zero quiz history.

**Implementation:** `helpers._fetch_user_performance_sync(user)` runs 3 cheap DB queries (aggregate stats, top 3 weak areas, due topics). Called inside both `_build_chatbot_prompt` (classic path) and `_build_agent_context` (agent tool-loop path) via `sync_to_async`. Errors are caught and logged — a failed query never breaks the chat.

## Platform Knowledge Store (`text_knowledge_store.py`)

A lightweight indexed-text retrieval module. No vector math.

- **Source file:** `backend/apps/chatbot/platform_kb/text_embeddings.json`
- **Format:** JSON where each entry maps a `chunk_id` to `{ heading, source_file, keywords, text }`
- **Indexing:** On startup, builds a token index (2+ char alphanumeric tokens) over each chunk's text, heading, and keywords.
- **`search(query, top_k)`** — scores chunks by: token overlap, keyword phrase match (+3.0), substring match (+2.5), heading match (+1.5). Returns ranked results.
- **`get_context(query, top_k, max_chars)`** — returns formatted top-k chunks safe to inject into a prompt.
- **`get_context(query, top_k, max_chars)`** — returns top-k relevant chunks for a query. Used by the active prompt path (injected per message).
- **`get_all_context()`** — returns every chunk concatenated. Available but no longer used in the prompt path.

The store is instantiated as a module-level singleton (`knowledge_store`) and imported in `helpers.py`.

## Platform Knowledge Base Files

Located in `backend/apps/chatbot/platform_kb/`:

| File | Content |
|---|---|
| `text_embeddings.json` | **Single source of truth.** All platform knowledge as manually maintained JSON chunks. Edited directly — no markdown source files. |
| `vector_embeddings.json` | Reserved for future neural vector embeddings (Tier 3). Empty until an embedding provider is configured. |

The markdown source files (`platform_overview.md`, `learning_tools.md`, etc.) have been deleted. `text_embeddings.json` is now edited directly. Each chunk has the shape `{ heading, source_file, keywords, text }`.

To add or update knowledge: edit `text_embeddings.json` directly. The store reloads on server restart.

## Legacy Retrieval (`platform_retrieval.py`)

`PlatformKnowledgeRetriever` is still present but not in the active prompt path. It was designed to load from the now-deleted markdown files. It will use `vector_embeddings.json` when neural embeddings are added (Tier 3).

The management command `python manage.py build_platform_kb_embeddings` generates `vector_embeddings.json` once an embedding provider (`CHATBOT_EMBEDDING_PROVIDER = openai | azure_openai`) is configured.

## File Upload

- Supported in the Django extraction pipeline for the `chat/file` endpoint.
- Extracted text is added as `document_context` in prompt construction.
- Supported formats: PDF, DOCX, PPTX, TXT (max 10 MB, max 50,000 chars after extraction).

## Streaming

`/api/chat/stream/` performs chunked response streaming from Django after a full FastAPI response arrives. This gives a typewriter UX without requiring provider-native streaming.

## Tutor Modes

The prompt builder accepts a `tutor_mode` parameter:

- `direct` (default) — answers questions clearly and concisely.
- `socratic` — guides students through questions rather than giving direct answers. Follows a strict Socratic protocol: ask what the student knows, build on correct thinking, ask one question at a time, only reveal the full answer after at least two guided exchanges.
