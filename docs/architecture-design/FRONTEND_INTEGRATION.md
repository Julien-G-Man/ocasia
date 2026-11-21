# Frontend Integration

## API Clients

- `frontend/src/services/api.js` -> general Django API client
- `frontend/src/services/auth.js` -> auth-specific client

Both attach `Authorization: Token <token>` when token exists in localStorage.

## Required Frontend Environment Variables

- `VITE_DJANGO_API_URL` (example: `http://localhost:8000/api`)

If missing, app boot fails by design.

## Warmup Endpoints

Derived in `services/api.js`:

- `DJANGO_WARMUP_ENDPOINT = {DJANGO_ROOT}/warmup/`

## Contract: Auth

- Login: `POST /auth/login/`
- Signup: `POST /auth/signup/`
- Me: `GET /auth/me/`
- Logout: `POST /auth/logout/`
- Verify email: `POST /auth/verify-email/`

## Contract: Quiz

- Extract text: `POST /quiz/ajax-extract-text/`
- Generate: `POST /quiz/generate/`
- Submit: `POST /quiz/submit/`
- Download: `POST /quiz/download/`
- History: `GET /quiz/history/`

## Contract: Flashcards

- Extract text: `POST /flashcards/ajax-extract-text/`
- Generate: `POST /flashcards/generate/`
- Save deck: `POST /flashcards/save/` (alias of `/flashcards/decks/save/`)
- List decks: `GET /flashcards/decks/`
- Deck cards: `GET /flashcards/deck/:id/` or `/flashcards/decks/:id/`
- Review: `POST /flashcards/review/`
- Explain: `POST /flashcards/explain/`

## Contract: AI Tutor

- Chat: `POST /tutor/chat/` — body: `{message, session_id, tutor_mode: "direct"|"socratic"}`
- Stream: `POST /tutor/chat/stream/` — same body; SSE events `session`, `tool_start`,
  `tool_done`, `token`, `done`, `error`
- File message: `POST /tutor/upload/` — multipart: `file` + `message`, `session_id`, `tutor_mode`
- Quiz from agent: `POST /tutor/quiz/from-agent/` — body: `{topic, num_questions, time_limit, session_id}`
- Session list: `GET /tutor/sessions/`
- Session detail: `GET /tutor/sessions/:id/` — full message history
- Rename session: `PATCH /tutor/sessions/:id/` — body: `{title}`
- Delete session: `DELETE /tutor/sessions/:id/`

## Error Handling Expectations

- 4xx: frontend should show non-breaking state and keep page usable.
- 5xx from AI-backed paths should degrade gracefully where fallback exists.
- Flashcards generation falls back to deterministic cards in the Django AI engine and React.