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
| `POST /agent/chat` | Django `chatbot_api_async` | Main chatbot — agent loop with `kb_search`, `search_web`, `request_quiz_form` |
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

Also:

- `/health/`
- `/warmup/`

## Data Ownership

- Quiz history: `apps.quiz.models.QuizSession`, `TopicPerformance`, `QuizTopicSchedule`
- Flashcards: `apps.flashcards.models.Deck`, `Flashcard`
- Chat: `apps.chatbot.models.ChatSession`, `ChatMessage`
- Users/auth: `apps.accounts.models.User`
- Payments: `apps.subscriptions.models.Donation`, `Subscription`, `PaymentHistory`

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
