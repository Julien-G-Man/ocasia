# Architecture

## Stack

- Frontend: React + Vite (`frontend/src`) — Vercel
- API gateway + persistence: Django (`backend/apps/*`) — Render
- Async AI worker: FastAPI (`ai_service/*`) — Render
- Database: PostgreSQL (Neon)
- Vector database: Upstash Vector (document RAG)
- Cache / channel layer: Redis (Upstash Redis)
- Embeddings: OpenAI `text-embedding-3-small`

## Core Pattern

1. React sends requests to Django (`/api/...`).
2. Django performs auth, validation, and database work.
3. For AI work, Django proxies to FastAPI with `X-Internal-Secret`.
4. FastAPI calls AI provider(s) and returns normalized output.
5. Django persists the result and returns it to React.

## Why This Split

- Django owns business logic, auth token checks, and models.
- FastAPI stays stateless and focused on async AI tasks.
- Internal shared-secret protection keeps worker endpoints private.
- Upstash Vector is owned entirely by FastAPI — Django never touches it.

## Service Communication

- Django → FastAPI base URL: `FASTAPI_BASE_URL`
- Internal auth header: `X-Internal-Secret`
- Shared value: `FASTAPI_SECRET` in both services

## Public vs Internal FastAPI Endpoints

- Public: `GET /health`
- Internal-only: `/agent/*`, `/quiz/*`, `/flashcards/*`
  - require valid `X-Internal-Secret`
  - browser-origin requests must be in `FASTAPI_ALLOWED_ORIGINS`

### FastAPI Agent Endpoints

| Endpoint | Caller | Purpose |
|---|---|---|
| `POST /agent/chat` | Django `chatbot_api_async` | Non-streaming chatbot — agent loop, returns complete JSON |
| `POST /agent/chat/stream` | Django `chatbot_stream_api_async` | SSE streaming chatbot — yields `tool_start`, `tool_done`, `token`, `done`, `error` events |
| `POST /agent/document/index` | Django `chatbot_file_api_async` (fire-and-forget) | Embed + store document chunks in Upstash Vector |
| `POST /agent/quiz/generate/` | Django `create_quiz_from_agent` | Standalone quiz generation from chatbot (no agent loop) |
| `POST /agent/orchestrate` | Internal / future features | Generic tool-loop endpoint |
| `GET /agent/tools` | Debug | List registered tools |
| `POST /agent/call` | Debug | Direct single-tool invocation |

## Warmup Model

React wakes both services on page load and every 10 minutes (`App.jsx`):

- Django: `GET {DJANGO_ROOT}/warmup/`
- FastAPI: `GET {FASTAPI_URL}/health`

## Main Django Route Mounts

From `backend/config/urls.py`:

- `/api/` + `apps.accounts.urls`
- `/api/` + `apps.chatbot.urls`
- `/api/` + `apps.quiz.urls`
- `/api/` + `apps.flashcards.urls`
- `/api/` + `apps.dashboard.urls`
- `/api/` + `apps.subscriptions.urls`
- `/api/` + `apps.clash.urls`
- `/clash/share/<room_code>/` → `clash_share_preview` (OG preview page)
- `/health/`, `/warmup/`

WebSocket routes (ASGI, `backend/config/asgi.py`):

- `ws/clash/<room_code>/` → `ClashConsumer`

## Data Ownership

- Quiz history: `apps.quiz.models.QuizSession`, `TopicPerformance`, `QuizTopicSchedule`
- Flashcards: `apps.flashcards.models.Deck`, `Flashcard`
- Chat: `apps.chatbot.models.ChatSession`, `ChatMessage`
- Users/auth: `apps.accounts.models.User`
- Payments: `apps.subscriptions.models.Donation`, `Subscription`, `PaymentHistory`
- Clash rooms: `apps.clash.models.ClashRoom`, `ClashParticipant`
- Document vectors: Upstash Vector (namespaced by `session_id`, not in PostgreSQL)

### Special ChatMessage Formats

`ChatMessage.content` is plain text for normal messages. The prefix `__QUIZ__:` marks
an inline quiz generated via the AI Tutor — the frontend detects this and renders a
Start Quiz card. The raw JSON is never forwarded to the LLM (summarised to a single line
in `_get_conversation_history`). The sidebar preview strips the JSON and shows
"Quiz generated: \<topic\>" via `dashboard_views._preview`.

### ChatSession Flags

| Field | Type | Purpose |
|---|---|---|
| `has_document` | `BooleanField` | Set to `True` after a file upload is indexed. Tells FastAPI to inject the `search_document` tool for all subsequent messages in this session. |

---

## Document RAG Architecture

When a user uploads a file in the chatbot:

```
React (FormData)
  │  POST /api/chat/file/
  ▼
Django chatbot_file_api_async
  ├── Extract text from file (PDF/DOCX/PPTX/TXT) — synchronous, in Django
  ├── chunk_text(text, size=500, overlap=100) → list[str]
  ├── asyncio.create_task(_index_document())  ← fire-and-forget
  │     └── POST /agent/document/index (FastAPI)
  │           └── OpenAI text-embedding-3-small (batch embed all chunks)
  │                 └── Upstash AsyncIndex.upsert(namespace=session_id)
  ├── ChatSession.has_document = True  ← mark session
  └── POST /agent/chat (FastAPI) with file_text=... for the initial analysis turn
```

On all subsequent messages in the same session:

```
Django chatbot_api_async
  ├── Reads session_obj.has_document == True
  └── POST /agent/chat { session_id, has_document: true, ... }
        ▼
     FastAPI /agent/chat
       ├── make_search_document_handler(session_id)  ← per-request handler factory
       ├── extra_tool_defs = [search_document ToolDefinition]
       └── _run_agent_loop(..., extra_tool_handlers={"search_document": handler})
             AI calls search_document(query="...")
               └── OpenAI embed(query) → Upstash AsyncIndex.query(namespace=session_id)
                     → top-5 relevant chunks returned to AI
```

### Upstash Vector namespacing

Each session gets its own namespace (`namespace=session_id`). Vectors from different
users never mix. The index uses:

- **Model:** `text-embedding-3-small` (1536 dimensions)
- **Distance metric:** Cosine
- **Metadata stored per vector:** `text`, `chunk_index`, `filename`, `session_id`

### RAG tool injection pattern

`search_document` is **not** in the global `TOOL_REGISTRY` handler — its handler is
built per-request with `make_search_document_handler(session_id)` which pre-binds the
session ID into the closure. This avoids any shared mutable state between sessions.

`_run_agent_loop` and `_run_agent_loop_stream` accept:
- `extra_tool_handlers: dict[str, async callable]` — dispatched before the global registry
- `extra_tool_defs: list[ToolDefinition]` — appended to the tools list sent to the AI

The definition exists in `TOOL_REGISTRY["search_document"]` for `get_definitions()` to
return its schema, but its `handler` key is `None` — it is never called from there.

---

## Authentication Architecture

### Token-Based Auth (DRF TokenAuthentication)

- **Flow:** User authenticates → Backend returns token → Frontend stores token → All requests include `Authorization: Token <key>`
- **Token rotation:** On every login (traditional or Google), old tokens are deleted and new token issued
- **Logout:** Explicitly deletes user's token server-side
- **No sessions:** Stateless authentication (no Django session cookies)

### Dual Authentication Methods

#### 1. Email/Username + Password
- Backend: Custom `EmailOrUsernameBackend` accepts either identifier
- Endpoints: `POST /api/auth/signup/`, `POST /api/auth/login/`
- Rate limited: 5 attempts per hour per IP

#### 2. Google OAuth 2.0
- **Custom implementation** (no django-allauth dependency)
- Backend: `apps.accounts.google_auth.py` — `GoogleAuthView` at `POST /api/auth/google/`
- Frontend: `@react-oauth/google` package
- **Token exchange flow:**
  1. Frontend: Google Sign-In SDK obtains Google ID token
  2. Frontend sends ID token to `POST /api/auth/google/`
  3. Backend verifies token with Google's servers
  4. Backend creates/updates user with `is_email_verified=True`
  5. Backend returns app auth token (same format as password login)
  6. Frontend stores token and proceeds to dashboard

- **Dependencies:**
  - Backend: `google-auth`, `google-auth-oauthlib`, `google-auth-httplib2`
  - Frontend: `@react-oauth/google`
  - Environment: `GOOGLE_OAUTH_CLIENT_ID` (backend and frontend must match)

### Frontend Auth Context

- Location: `frontend/src/context/AuthContext.jsx`
- Wraps app with auth state (`user`, `isAuthenticated`, `isLoading`)
- Methods: `login()`, `signup()`, `googleAuth()`, `logout()`
- Rehydrates auth from localStorage on page load
- `ProtectedRoute` component holds render until `isLoading=false` to prevent
  premature redirects on hard refresh

---

## WebSocket Architecture (Clash)

### Overview

```
React (ClashLobby / ClashPlay)
    │  ws://<host>/ws/clash/<room_code>/?token=<DRF token>
    ↓
Django Channels ASGI router  (backend/config/asgi.py)
    ↓
ClashConsumer  (AsyncJsonWebsocketConsumer)
    ↓
Redis Channel Layer  (channels_redis — one group per room, Upstash Redis)
    ↓
Django cache  (live game state per room, TTL 2h)
    ↓
PostgreSQL  (ClashRoom, ClashParticipant — persisted at game end)
```

## File Storage (Cloudinary)

Material images and uploaded files are stored in Cloudinary and served via its CDN.
Django handles the upload logic; files are never written to local disk.

```
React (FormData)
  │  POST /api/materials/upload/
  ▼
Django materials view
  ├── Validate file
  ├── Upload to Cloudinary → returns CDN URL
  └── Store URL in Material.file_url (PostgreSQL)
```

---

## Redis Caching (View-Level)

In addition to the channel layer, Redis is used for response-level caching via Django's
`cache` framework (`from django.core.cache import cache`).

| Cache key pattern | TTL | Busted when |
|---|---|---|
| `dash:stats:{user_id}` | 60s | User submits a quiz |
| `quiz:hist:{user_id}` | 60s | User submits a quiz |
| `quiz:weak:{user_id}` | 120s | User submits a quiz |
| `quiz:due:{user_id}` | 60s | User submits a quiz |
| `flash:hist:{user_id}` | 120s | User saves a flashcard deck |
| `admin:stats` | 120s | Any quiz submitted or deck saved |
| `admin:trends:{days}` | 120s | Not explicitly busted (short TTL sufficient) |

All bust operations use `cache.delete_many([...])` immediately after the write that
invalidates them. Async views wrap this in `await sync_to_async(cache.delete_many)(...)`.

---

### Channel Layer

Configured in `settings.py` when `REDIS_URL` env var is set:

```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}
```

Falls back to `InMemoryChannelLayer` when `REDIS_URL` is absent (local dev only —
does not support multiple workers).

### ClashConsumer Lifecycle

1. `connect()` — validate DRF token, load room, join channel group, send `game_catchup` if mid-game.
2. `receive_json()` — dispatches `start_game` (host only) or `submit_answer`.
3. `disconnect()` — set `self.connected = False`, remove from group, re-broadcast lobby.

### Game Loop

`handle_start_game()` creates an `asyncio.Task` and stores it in
`ClashConsumer._game_tasks[room_code]` (class-level dict). The task persists
across the host's disconnect/reconnect within the same worker process.

```
countdown (asyncio.sleep 3s)
→ for each question:
    broadcast clash.new_question  (records question_start_time in Redis)
    poll every 1.0s — break if all answered or timer expires
    broadcast clash.question_ended  (answer + explanation + top3)
    asyncio.sleep(10s)  — reveal pause (read answer + leaderboard)
→ broadcast clash.game_finished
→ persist scores, ranks, and per-question answers to DB
```

Participant count is re-fetched at the start of each question iteration so
disconnected players don't stall the "all answered" check.

### Event Type Mapping

Django Channels routes group_send messages using `type` field dots→underscores:

| `type` (in group_send) | Handler method |
|---|---|
| `clash.player_joined` | `clash_player_joined` |
| `clash.game_starting` | `clash_game_starting` |
| `clash.new_question` | `clash_new_question` |
| `clash.question_ended` | `clash_question_ended` |
| `clash.game_finished` | `clash_game_finished` |

The frontend must check against the dot-notation string (e.g. `case "clash.new_question"`).

### `_safe_send` Pattern

All channel-layer event handlers call `_safe_send(event)` instead of `send_json(event)`
directly. This guards against the `RuntimeError: Unexpected ASGI message 'websocket.send'`
crash that occurs when a broadcast reaches a consumer whose WebSocket has already closed:

```python
async def _safe_send(self, event):
    if not self.connected:
        return
    try:
        await self.send_json(event)
    except Exception:
        pass
```

### Scoring

```
correct answer → BASE_POINTS (1000) + SPEED_BONUS_MAX (500) × (1 − elapsed/time_limit)
wrong / no answer → 0
max per question → 1500 pts
```

`elapsed` is computed server-side from `question_start_time` stored in Redis when the
question is broadcast. The client never supplies timing — `elapsed_ms` is not accepted.

---

## Clash Share Link (OG Preview)

Invitees receive a **frontend URL**: `https://ocasia.vercel.app/clash/share/<code>/`

When a social media bot crawls that URL, Vercel rewrites it to the Django backend which
returns an HTML page with Clash-specific Open Graph tags (`clash-fist.jpg` as the preview
image) and a `<meta http-equiv="refresh">` that immediately redirects real users to the
lobby (`/clash/lobby/<code>`).

```
Vercel vercel.json rewrite:
  /clash/share/:code/ → https://lamla-api.onrender.com/clash/share/:code/

Django clash_share_preview view:
  → Returns HTML with og:title, og:image (clash-fist.jpg), og:description
  → meta-refresh to frontend /clash/lobby/<code>

Bot:  reads OG tags → rich preview with fist image
User: meta-refresh → /clash/lobby/<code> → ClashLobby component
```

---

## Logging

### Django

Configured via `LOGGING` dict in `settings.py`. All `apps.*` loggers show `INFO+`; Django
internals stay at `WARNING`. Format: `[LEVEL] logger.name — message`.

### FastAPI

Configured via `logging.config.dictConfig` in `main.py`. The `agent`, `services`, and
`core` logger namespaces show `INFO+`. Third-party SDKs (`httpx`, `anthropic`, `openai`)
are suppressed to `WARNING`. Uvicorn is separately configured with `log_level="info"`.

---

## Observability (Sentry)

Both services initialise Sentry at startup when `SENTRY_DSN` is set.

| Service | Integration | Config location |
|---|---|---|
| Django | `DjangoIntegration()` | top of `settings.py` |
| FastAPI | `StarletteIntegration()` + `FastApiIntegration()` | top of `main.py` |

**Environment variables (both services):**

| Variable | Default | Purpose |
|---|---|---|
| `SENTRY_DSN` | *(unset — disables Sentry)* | Project DSN from Sentry dashboard |
| `ENVIRONMENT` | `"development"` | Tags events as `production`, `staging`, etc. |
| `SENTRY_TRACES_SAMPLE_RATE` | `"0.1"` | Fraction of transactions sent as performance traces |

Setting `SENTRY_DSN` to an empty string (or omitting it) is safe — Sentry will not initialise
and no exceptions are thrown. This keeps local dev unaffected.
