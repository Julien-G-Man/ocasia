# Ocasia

An AI-powered academic learning platform — quiz generation, spaced-repetition flashcards,
a tool-calling AI tutor with document RAG, live multiplayer quiz battles (Clash), and
performance tracking. Built by students at KNUST, Ghana.

## Tech Stack

| Layer | Technology | Role |
|---|---|---|
| Frontend | React + Vite | Web app — hosted on Vercel |
| API + AI runtime | Django + Django REST Framework | Auth, persistence, sessions, and the in-process LangChain tutor agent |
| Tutor agent | Django + LangChain (`langchain-core`, `langchain-openai`) | Tool-calling loop, SSE streaming, RAG tools |
| Vector database | PostgreSQL + pgvector | Tutor document embeddings (HNSW cosine index) |
| Database | PostgreSQL (Neon) | All relational data, including tutor sessions and messages |
| Cache / channel layer | Redis (Upstash Redis) | Django Channels WebSocket pub/sub (Clash) + view-level response caching (dashboard, quiz, flashcards, admin stats) |
| Realtime | Django Channels + ASGI | WebSocket connections for live Clash game |
| Embeddings | OpenAI `text-embedding-3-small` | Document chunking → pgvector search |
| Primary AI | OpenAI | Tool use, agent loop, content generation |
| AI fallbacks | Claude, NVIDIA NIM, Azure OpenAI, DeepSeek, Gemini, HuggingFace | Provider cascade on failure |
| Payments | Paystack | Donation payment processing — initiate, verify, webhook |
| File storage | Cloudinary | Material images and uploaded files — served via Cloudinary CDN |
| Hosting | Render (Django), Vercel (React) | Production deployment |
| Legacy (retiring) | `chatbot` app | Still mounted at `/api/chat/*` and `/api/chatbot/history/`, but no active frontend feature calls it |

## Start Here

- Setup guide: `docs/setup-configuration/GETTING_STARTED.md`
- Quick reference: `docs/setup-configuration/QUICK_REFERENCE.md`
- Architecture: `docs/architecture-design/ARCHITECTURE.md`
- Agent + RAG: `docs/architecture-design/AGENT_IMPLEMENTATION.md`
- Tutor RAG (pgvector): `docs/architecture-design/TUTOR_RAG_PGVECTOR.md`
- Tutor feature: `docs/features/TUTOR.md`
- Frontend routes: `docs/frontend/ROUTES_AND_PAGES.md`
- Security: `docs/security-reference/SECURITY.md`

## Service Map

```
Browser
  │
  ├─── HTTPS ──► Vercel (React SPA)
  │                └── /clash/share/:code/ ──► Render (Django) [OG preview + redirect]
  │
  └─── HTTPS ──► Render (Django :8000)
                  ├── auth, tutor, quiz, flashcards, dashboard, materials, clash
                  ├── tutor agent (LangChain) ──► OpenAI / Claude / NVIDIA / Azure / ...
                  ├── tutor RAG ──► PostgreSQL + pgvector
                  ├── material uploads ──► Cloudinary (file storage + CDN)
                  └── ws://.../ws/clash/:code/ ──► Django Channels
                                                  └── Upstash Redis (channel layer)
```

Legacy code only: the `chatbot` app remains as unused legacy code. All quiz AI work now
runs in-process inside Django.

## Local Development

**1. Django (API + tutor, port 8000)**
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python run.py --port 8000 --reload
```

**2. React (frontend, port 5173)**
```bash
cd frontend
npm install
npm run dev
```

## Health Checks

- Django: `GET /health/`

## Retiring the Split Architecture

The platform originally ran two services: Django as an API gateway and a separate
FastAPI `ai_service` that owned the agent loop, prompts, tool calling, and vector
indexing. The AI tutor, flashcards, and most AI work now run in-process inside Django.

### Gains

- **One deployable.** One process to build, deploy, monitor, and roll back.
- **No internal network hop.** No `X-Internal-Secret` calls, no second health check,
  and no cross-service failure mode between Django and the AI layer.
- **Shared platform primitives.** Auth, cache, ORM, settings, and logging are reused by
  AI features instead of being duplicated or proxied.
- **Simpler local setup.** One backend process instead of two.

### Trade-offs

- **Shared worker budget.** AI work runs on the Django worker's event loop, so long or
  heavy tool calls need per-tool timeouts and bounded concurrency (already implemented).
- **Fewer scaling axes.** API and AI workloads scale together instead of independently.
- **Larger Django image.** LangChain and provider SDKs ship with the API process.
- **One blast radius.** A deploy or rollback affects API and AI behavior together.

### Status

- **Tutor:** Django-native (LangChain agent, pgvector RAG, SSE streaming).
- **Flashcards:** Django-native.
- **Quiz generation and short-answer evaluation:** still proxied to FastAPI.
- The `chatbot` app is retained only for its unused legacy HTTP endpoints; `ai_service`
  remains deployed for quiz. Both can be removed once quiz is migrated.

## Key Design Rules

- **Django owns auth, persistence, and the tutor agent loop.**
- **The tutor streams SSE directly from Django** — the browser never calls FastAPI.
- **RAG is pgvector-backed** and scoped by document/session, not an external vector DB.
- **Per-tool timeouts and normalized errors** keep a slow tool from hanging a turn.
- Use `docs/README.md` as the canonical documentation index.