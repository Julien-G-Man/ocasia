# Render Deployment Guide (Django + legacy FastAPI)

Django is the primary service. The legacy FastAPI `ai_service` is still deployed for
flashcard generation/explanation and Clash quiz generation.

## Service Layout

- Service 1: Django API + tutor agent (`backend`)
- Service 2: FastAPI worker (`ai_service`) — legacy, flashcards and Clash only
- Frontend runs separately (Vercel)

## Django Service

### Start command

```bash
python run_django.py --port 10000 --no-reload --workers 4
```

(Or Render-managed equivalent using `uvicorn lamla.asgi:application ...`.)

### Required environment

- `SECRET_KEY`
- `DEBUG=False`
- `DATABASE_URL`
- `FASTAPI_BASE_URL=<fastapi-render-url>`
- `FASTAPI_SECRET=<shared-secret>`
- `CORS_ALLOWED_ORIGINS=<frontend-origins>`
- `CSRF_TRUSTED_ORIGINS=<frontend-origins>`

## Legacy FastAPI Service

### Start command

```bash
python run.py
```

### Required environment

- `FASTAPI_SECRET=<same-as-django>`
- `FASTAPI_ALLOWED_ORIGINS=<frontend + django origins>`
- provider keys (`AZURE_*`, others as used)

## CORS and Internal Access Rules

- Keep `GET /health` public for wake/probe checks.
- All other FastAPI routes require `X-Internal-Secret`.
- Include both Django and frontend origins in `FASTAPI_ALLOWED_ORIGINS` to prevent cross-origin blocks when needed.

## Verify After Deploy

- Django `GET /health/` returns 200
- FastAPI `GET /health` returns 200
- Django can call legacy FastAPI internal endpoints (flashcards, Clash quiz generation)
- Frontend login + quiz + flashcards + chat work end-to-end
