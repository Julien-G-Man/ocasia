# Architecture

## Stack

- Frontend: React (`frontend/src`)
- API gateway + persistence: Django (`backend/apps/*`)
- Async AI worker: FastAPI (`ai_service/*`)

## Core Pattern

1. React sends requests to Django (`/api/...`).
2. Django performs auth, validation, and database work.
3. For AI work, Django proxies to FastAPI with `X-Internal-Secret`.
4. FastAPI calls AI provider(s) and returns normalized output.
5. Django returns response to React.

## Why This Split

- Django owns business logic, auth token checks, and models.
- FastAPI stays stateless and focused on async AI tasks
- Internal shared-secret protection keeps worker endpoints private by default.

## Service Communication

- Django -> FastAPI base URL: `FASTAPI_BASE_URL`
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
| `POST /agent/quiz/generate/` | Django `create_quiz_from_agent` | Standalone quiz generation from chatbot (no agent loop) |
| `POST /agent/orchestrate` | Internal / future features | Generic tool-loop endpoint |
| `GET /agent/tools` | Debug | List registered tools |
| `POST /agent/call` | Debug | Direct single-tool invocation |

## Warmup Model

React wakes both services:

- Django: `GET {DJANGO_ROOT}/warmup/`
- FastAPI: `GET {FASTAPI_URL}/health`

Executed on page load and every 10 minutes (`App.jsx`).

## Main Django Route Mounts

From `backend/config/urls.py`:

- `/api/` + `apps.accounts.urls`
- `/api/` + `apps.chatbot.urls`
- `/api/` + `apps.quiz.urls`
- `/api/` + `apps.flashcards.urls`
- `/api/` + `apps.dashboard.urls`
- `/api/` + `apps.subscriptions.urls`
- `/api/` + `apps.clash.urls`

Also:

- `/health/`
- `/warmup/`

WebSocket routes (ASGI, `backend/config/asgi.py`):

- `ws/clash/<room_code>/` → `ClashConsumer`

## Data Ownership

- Quiz history: `apps.quiz.models.QuizSession`, `TopicPerformance`, `QuizTopicSchedule`
- Flashcards: `apps.flashcards.models.Deck`, `Flashcard`
- Chat: `apps.chatbot.models.ChatSession`, `ChatMessage`
- Users/auth: `apps.accounts.models.User`
- Payments: `apps.subscriptions.models.Donation`, `Subscription`, `PaymentHistory`
- Clash rooms: `apps.clash.models.ClashRoom`, `ClashParticipant`

### Special ChatMessage Formats

`ChatMessage.content` is plain text for normal messages. The prefix `__QUIZ__:` marks
an inline quiz generated via the AI Tutor — the frontend detects this and renders a
Start Quiz card. The raw JSON is never forwarded to the LLM (summarised to a single line
in `_get_conversation_history`). The sidebar preview strips the JSON and shows
"Quiz generated: \<topic\>" via `dashboard_views._preview`.

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
- Backend: `apps.accounts.google_auth.py` - `GoogleAuthView` at `POST /api/auth/google/`
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
- All auth methods update context state before navigation (no page reload needed)

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
Redis Channel Layer  (channels_redis — one group per room)
    ↓
Django cache  (live game state per room, TTL 2h)
    ↓
PostgreSQL  (ClashRoom, ClashParticipant — persisted at game end)
```

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
    broadcast clash.new_question
    poll every 0.5s — break if all answered or timer expires
    broadcast clash.question_ended  (answer + explanation + top3)
    asyncio.sleep(3s)  — reveal pause
→ broadcast clash.game_finished
→ persist scores + ranks to DB
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
