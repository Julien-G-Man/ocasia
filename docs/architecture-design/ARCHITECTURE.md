# Architecture

## Stack

- Frontend: React + Vite (`frontend/src`) — Vercel
- API + AI runtime: Django (`backend/apps/*`) — Render
- Tutor agent: Django + LangChain (`apps/tutor/agent/`) — in-process
- Vector database: PostgreSQL + pgvector (tutor document RAG)
- Database: PostgreSQL (Neon)
- Cache / channel layer: Redis (Upstash Redis)
- Embeddings: OpenAI `text-embedding-3-small`
- Legacy (retiring): FastAPI (`ai_service/*`) — still used by flashcards and Clash quiz generation

## Core Pattern

1. React sends requests to Django (`/api/...`).
2. Django performs auth, validation, persistence, and — for the tutor — the agent loop.
3. AI work calls providers directly through `apps.core.ai_engine` (or LangChain for the tutor).
4. Django persists the result and returns it (or streams SSE) to React.

## Why In-Process

- One deployable and one process to operate.
- No internal `X-Internal-Secret` hop between Django and an AI worker.
- Auth, cache, ORM, settings, and logging are shared by AI features.
- Simpler local setup.

Trade-offs: AI work shares the Django worker's event loop (mitigated with per-tool
timeouts), fewer independent scaling axes, a larger Django image, and a single
deploy/rollback blast radius.

## Legacy FastAPI Service (Retiring)

The FastAPI `ai_service` still handles flashcard generation/explanation and Clash quiz
generation. It is internal-only and will be removed once those callers move in-process.

- Django → FastAPI base URL: `FASTAPI_BASE_URL`
- Internal auth header: `X-Internal-Secret`
- Shared value: `FASTAPI_SECRET` in both services

## Public vs Internal FastAPI Endpoints (Legacy)

- Public: `GET /health`
- Internal-only: `/agent/*`, `/quiz/*`, `/flashcards/*`
  - require valid `X-Internal-Secret`
  - browser-origin requests must be in `FASTAPI_ALLOWED_ORIGINS`

### FastAPI Endpoints (Legacy)

| Endpoint | Caller | Purpose |
|---|---|---|
| `POST /quiz/` | Django Clash views | Clash question generation |
| `POST /flashcards/generate` | Django flashcards views | Flashcard generation |
| `POST /flashcards/explain` | Django flashcards views | Answer explanation |
| `POST /agent/call` | Legacy chatbot views | Single-tool calls |

## Warmup Model

React wakes Django on page load and every 10 minutes (`App.jsx`):
`GET {DJANGO_ROOT}/warmup/`

## Main Django Route Mounts

From `backend/config/urls.py`:

- `/api/` + `apps.accounts.urls`
- `/api/` + `apps.tutor.urls`
- `/api/` + `apps.quiz.urls`
- `/api/` + `apps.flashcards.urls`
- `/api/` + `apps.dashboard.urls`
- `/api/` + `apps.materials.urls`
- `/api/` + `apps.subscriptions.urls`
- `/api/` + `apps.clash.urls`
- `/api/` + `apps.chatbot.urls` (legacy; retiring)
- `/clash/share/<room_code>/` → `clash_share_preview` (OG preview page)
- `/health/`, `/warmup/`

WebSocket routes (ASGI, `backend/config/asgi.py`):

- `ws/clash/<room_code>/` → `ClashConsumer`

## Data Ownership

- Quiz history: `apps.quiz.models.QuizSession`, `TopicPerformance`, `QuizTopicSchedule`
- Flashcards: `apps.flashcards.models.Deck`, `Flashcard`
- Tutor: `apps.tutor.models.TutorSession`, `TutorMessage`
- Users/auth: `apps.accounts.models.User`
- Payments: `apps.subscriptions.models.Donation`, `Subscription`, `PaymentHistory`
- Clash rooms: `apps.clash.models.ClashRoom`, `ClashParticipant`
- Document vectors: PostgreSQL + pgvector (`TutorDocument`, `TutorDocumentChunk`)
- Legacy chat: `apps.chatbot.models.ChatSession`, `ChatMessage` (retiring; no longer used by the dashboard)

### Special TutorMessage Formats

`TutorMessage.content` is plain text for normal messages. The prefix `__QUIZ__:` marks
an inline quiz generated via the AI Tutor — the frontend detects this and renders a
Start Quiz card. The raw JSON is never forwarded to the LLM (summarised to a single line
in `history_for_session`). The sidebar preview strips the JSON and shows
"Quiz generated: \<subject\>" via `conversations.preview_message`.

### TutorSession Flags

| Field | Type | Purpose |
|---|---|---|
| `has_document` | `BooleanField` | Set to `True` after a file upload is indexed. Keeps the session marked so follow-up turns can rely on `search_document`. |

---

## Document RAG Architecture

The tutor uses a shared `RAGEngine` singleton with PostgreSQL + pgvector. Retrieval
combines vector cosine similarity and BM25 lexical ranks via reciprocal-rank fusion.

### Upload flow

```
React (FormData)
  │  POST /api/tutor/upload/
  ▼
Django TutorDocumentUploadView
  ├── Extract text from file (PDF/DOCX/PPTX/TXT) — in Django
  ├── TutorAgent runs immediately with file_text=... (first response, no wait)
  ├── _maybe_index_upload(...) — best-effort, fire-and-forget
  │     ├── chunk text (800 chars, 120 overlap)
  │     ├── embed with text-embedding-3-small (1536 dims)
  │     └── upsert TutorDocument + TutorDocumentChunk (pgvector HNSW)
  └── TutorSession.has_document = True
```

### Follow-up turns

`TutorAgent` injects `session_id` into `search_document`. When the model decides the
document is relevant it calls `search_document(query="...")`; the tool embeds the query
and retrieves the top passages from pgvector.

### Storage

- `TutorDocument` tracks each indexed source, content checksum, and indexing version.
- `TutorDocumentChunk` stores text, page/slide number, metadata, and a 1536-dimensional
  embedding.
- An HNSW cosine index supports nearest-neighbor search.
- The current tool searches a shared corpus and does not apply per-user document
  permissions.

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

Invitees receive a **frontend URL**: `https://ocasia.live/clash/share/<code>/`

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

Configured via the `LOGGING` dict in `settings.py`. All `apps.*` loggers show `INFO+`;
Django internals stay at `WARNING`. Format: `[LEVEL] logger.name — message`.

The legacy FastAPI service keeps its own `logging.config.dictConfig` in `main.py`.

---

## Observability (Sentry)

Django initialises Sentry at startup when `SENTRY_DSN` is set.

| Service | Integration | Config location |
|---|---|---|
| Django | `DjangoIntegration()` | top of `settings.py` |
| FastAPI (legacy) | `StarletteIntegration()` + `FastApiIntegration()` | top of `main.py` |

**Environment variables (Django and legacy FastAPI):**

| Variable | Default | Purpose |
|---|---|---|
| `SENTRY_DSN` | *(unset — disables Sentry)* | Project DSN from Sentry dashboard |
| `ENVIRONMENT` | `"development"` | Tags events as `production`, `staging`, etc. |
| `SENTRY_TRACES_SAMPLE_RATE` | `"0.1"` | Fraction of transactions sent as performance traces |

Setting `SENTRY_DSN` to an empty string (or omitting it) is safe — Sentry will not initialise
and no exceptions are thrown. This keeps local dev unaffected.
