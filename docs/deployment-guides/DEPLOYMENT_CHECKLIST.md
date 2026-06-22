# Deployment Checklist

Use this before every production deploy.

## Environment

- Django and FastAPI have matching `FASTAPI_SECRET`.
- Django `FASTAPI_BASE_URL` points to live FastAPI service.
- Frontend `VITE_DJANGO_API_URL` and `VITE_FASTAPI_URL` are valid absolute URLs.
- All URLs include `http://` or `https://`.
- **Google OAuth (if enabled):**
  - Django `GOOGLE_OAUTH_CLIENT_ID` matches frontend `VITE_GOOGLE_CLIENT_ID`
  - Production domain added to Google Cloud Console authorized origins
  - Different OAuth credentials used for production vs development
- **EmailJS (auth emails):**
  - `VITE_EMAILJS_PUBLIC_KEY`, `VITE_EMAILJS_SERVICE_ID` set in frontend env
  - `VITE_EMAILJS_TEMPLATE_VERIFY`, `VITE_EMAILJS_TEMPLATE_RESET`, and `VITE_EMAILJS_TEMPLATE_WELCOME` point to live templates
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

## Payments (Paystack)

- `PAYSTACK_SECRET_KEY` (live key — `sk_live_...`) and `PAYSTACK_PUBLIC_KEY` (`pk_live_...`) are set in Render environment.
- Paystack webhook URL in the Paystack dashboard must include a trailing slash:
  ```
  https://<your-api>.onrender.com/api/subscriptions/webhook/
  ```
  Without the trailing slash, Django's `APPEND_SLASH` redirects POST → GET (301) and the webhook is never received. The backend also registers the no-slash path as a fallback, but the Paystack dashboard URL should always use the slash.

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
- **Donation smoke test:**
  1. Visit `/donate` as a guest — form loads, "Support Us" button visible in navbar.
  2. Enter an amount (min GHS 5) and email, submit — redirected to Paystack hosted page.
  3. Complete a real or test payment — redirected to `/donate/thank-you`.
  4. Thank-you page shows "Payment received" and donor's name/amount.
  5. Check Render logs for `Webhook event: charge.success ref=<ref>` and `Donation <ref> confirmed`.
  6. Cancel a payment mid-flow — thank-you page shows "Payment cancelled, no charge was made."

## Error Handling

- 5xx responses do not break frontend state.
- Flashcards show fallback cards when provider is down.
