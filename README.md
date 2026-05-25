# Lamla AI

An AI-powered academic learning platform — quiz generation, spaced-repetition flashcards,
a tool-calling AI tutor, a community file library, and performance tracking.
Built by students at KNUST, Ghana.

## Tech Stack

| Layer | Technology | Role |
|---|---|---|
| Frontend | React | Web app |
| API gateway | Django | Auth, persistence, session management |
| AI service | FastAPI | Agent loop, tool calling, KB search, LLM calls |
| Database | PostgreSQL (Neon in prod) | All persistent data |

## Start Here

- Setup guide: `docs/setup-configuration/GETTING_STARTED.md`
- Quick reference: `docs/setup-configuration/QUICK_REFERENCE.md`
- Architecture: `docs/architecture-design/ARCHITECTURE.md`
- Agent implementation: `docs/architecture-design/AGENT_IMPLEMENTATION.md`
- Frontend routes: `docs/frontend/ROUTES_AND_PAGES.md`
- Security: `docs/security-reference/SECURITY.md`

## Local Development

**1. Django (API gateway)**
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python run.py --port 8000 --reload
```

**2. FastAPI (AI service)**
```bash
cd ai_service
pip install -r requirements.txt
python run.py
```

**3. React (frontend)**
```bash
cd frontend
npm install
npm run dev
```

## Health Checks

- Django: `GET /health/`
- FastAPI: `GET /health`

## Notes

- Django owns all DB work. FastAPI owns all AI work.
- Keep documentation updates in the same PR as behavior/API changes.
- Use `docs/README.md` as the canonical documentation index.
