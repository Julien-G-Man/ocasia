# Getting Started

## Prerequisites

- Python 3.11+
- Node 18+
- PostgreSQL

## 1) Backend install

```bash
cd backend
pip install -r requirements.txt
```

Create `backend/.env` with at least:

```bash
SECRET_KEY=change-me
DEBUG=True
POSTGRES_DB_NAME=lamla_db
POSTGRES_DB_USER=postgres
POSTGRES_DB_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
FASTAPI_BASE_URL=http://localhost:8001
FASTAPI_SECRET=change-me-shared-secret
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CSRF_TRUSTED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Optional: Google OAuth (see docs/authentication/GOOGLE_OAUTH.md)
# GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
# GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret

# Optional: Paystack (required for donations — use test keys locally)
# PAYSTACK_PUBLIC_KEY=pk_test_...
# PAYSTACK_SECRET_KEY=sk_test_...
```

Run migrations:

```bash
python manage.py migrate
```

Start Django (ASGI):

```bash
python run_django.py --port 8000 --reload
```

## 2) FastAPI install/run

```bash
cd ai_service
python run.py
```

Set shared env values for FastAPI process (or `ai_service/.env`):

```bash
FASTAPI_SECRET=change-me-shared-secret
FASTAPI_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000,https://ocasia.live,https://ocasia.vercel.app,https://lamla-api.onrender.com
```

## 3) Frontend install/run

```bash
cd frontend
npm install
npm start
```

Frontend env (example `.env` in `frontend/`):

```bash
REACT_APP_DJANGO_API_URL=http://localhost:8000/api
REACT_APP_FASTAPI_URL=http://localhost:8001

# Optional: Google OAuth (must match backend GOOGLE_OAUTH_CLIENT_ID)
# REACT_APP_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

## 4) Smoke test

- `GET http://localhost:8000/health/`
- `GET http://localhost:8000/warmup/`
- `GET http://localhost:8001/health`
- login/signup from frontend
