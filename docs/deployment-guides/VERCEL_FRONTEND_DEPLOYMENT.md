# Vercel Frontend Deployment

## Build

From `frontend/`:

```bash
npm install
npm run build
```

## Required Environment Variables

- `VITE_DJANGO_API_URL=https://<django-host>/api`

Use full URLs including protocol.

## Runtime Expectations

- App pings Django `/warmup/` on load and every 10 minutes.

## Common Failures

### Missing protocol

Error: URL missing `http://` or `https://`

Fix: update env vars with absolute URLs.

### CORS failures

Fix:

- Add frontend URL to Django `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`
- Add the Django URL to the legacy FastAPI `FASTAPI_ALLOWED_ORIGINS` (flashcards and Clash calls)

### Build failure for missing CSS import

Ensure filename casing matches import exactly (for Linux CI).
