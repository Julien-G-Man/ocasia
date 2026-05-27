# Deployment Checklist

Use this before every production deploy.

## Environment

- Django and FastAPI have matching `FASTAPI_SECRET`.
- Django `FASTAPI_BASE_URL` points to live FastAPI service.
- Frontend `REACT_APP_DJANGO_API_URL` and `REACT_APP_FASTAPI_URL` are valid absolute URLs.
- All URLs include `http://` or `https://`.
- **Google OAuth (if enabled):**
  - Django `GOOGLE_OAUTH_CLIENT_ID` matches frontend `REACT_APP_GOOGLE_CLIENT_ID`
  - Production domain added to Google Cloud Console authorized origins
  - Different OAuth credentials used for production vs development
- **EmailJS (auth emails):**
  - `REACT_APP_EMAILJS_PUBLIC_KEY`, `REACT_APP_EMAILJS_SERVICE_ID` set in frontend env
  - `REACT_APP_EMAILJS_TEMPLATE_VERIFY`, `REACT_APP_EMAILJS_TEMPLATE_RESET`, and `REACT_APP_EMAILJS_TEMPLATE_WELCOME` point to live templates
  - Templates have `{{to_email}}` set as the "To Email" field in EmailJS dashboard
- **Clash (WebSocket / multiplayer):**
  - `REDIS_URL` set to a standard Redis protocol URL: `rediss://default:<token>@<host>.upstash.io:6379` (Upstash) or equivalent. **Without this, WebSockets fall back to `InMemoryChannelLayer` which does not support multiple workers.**
  - `ALLOWED_HOSTS` env var set to a comma-separated list of allowed hostnames (e.g. `yourdomain.onrender.com,www.yourfrontend.com`). `settings.py` reads this and also auto-appends `RENDER_EXTERNAL_HOSTNAME` if set.

## Allowed Origins

- Django `CORS_ALLOWED_ORIGINS` includes production frontend URL(s).
- Django `CSRF_TRUSTED_ORIGINS` includes same trusted web origins.
- FastAPI `FASTAPI_ALLOWED_ORIGINS` includes:
  - frontend origin(s)
  - Django origin(s) (`localhost:8000` and deployed Django host)

## Health and Wake

- `GET /health/` works on Django service.
- `GET /health` works on FastAPI service.
- Frontend warmup runs at load and every 10 minutes.

## Smoke Tests

- Login/signup flow succeeds (email/username + password).
- **Google OAuth login/signup works** (if enabled, test "Continue with Google" button).
- Quiz generation works.
- Flashcard extraction + generation + save + study review works.
- Chat message and file chat work.
- Dashboard stats and home contact/newsletter endpoints work.
- **Clash smoke test:**
  1. User A creates a room (topic + settings) — room code returned.
  2. User B joins with the room code — both appear in the lobby participant list.
  3. User A starts the clash — both see 3-2-1 countdown and first question.
  4. Both submit answers — `answer_confirmed` received, leaderboard updates.
  5. Game completes — final rankings shown on results page.

## Error Handling

- 5xx responses do not break frontend state.
- Flashcards show fallback cards when provider is down.
