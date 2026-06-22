# Ocasia

An AI-powered academic learning platform — quiz generation, spaced-repetition flashcards,
a tool-calling AI tutor with document RAG, live multiplayer quiz battles (Clash), and
performance tracking. Built by students at KNUST, Ghana.

## Tech Stack

| Layer | Technology | Role |
|---|---|---|
| Frontend | React + Vite | Web app — hosted on Vercel |
| API gateway | Django + Django REST Framework | Auth, persistence, session management, proxying |
| AI service | FastAPI + Uvicorn | Agent loop, tool calling, LLM calls, vector indexing |
| Database | PostgreSQL (Neon) | All relational data |
| Vector database | Upstash Vector | Document chunk embeddings for chatbot RAG |
| Cache / channel layer | Redis (Upstash Redis) | Django Channels WebSocket pub/sub (Clash) + view-level response caching (dashboard, quiz, flashcards, admin stats) |
| Realtime | Django Channels + ASGI | WebSocket connections for live Clash game |
| Embeddings | OpenAI `text-embedding-3-small` | Document chunking → vector search |
| Primary AI | OpenAI | Tool use, agent loop, content generation |
| AI fallbacks | Claude, NVIDIA NIM, Azure OpenAI, DeepSeek, Gemini, HuggingFace | Provider cascade on failure |
| File storage | Cloudinary | Material images and uploaded files — served via Cloudinary CDN |
| Hosting | Render (Django + FastAPI), Vercel (React) | Production deployment |

## Start Here

- Setup guide: `docs/setup-configuration/GETTING_STARTED.md`
- Quick reference: `docs/setup-configuration/QUICK_REFERENCE.md`
- Architecture: `docs/architecture-design/ARCHITECTURE.md`
- Agent + RAG: `docs/architecture-design/AGENT_IMPLEMENTATION.md`
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
                  ├── auth, quiz, flashcards, dashboard, chatbot, clash views
                  ├── material uploads ──► Cloudinary (file storage + CDN)
                  ├── ws://.../ws/clash/:code/  ──► Django Channels
                  │                                   └── Upstash Redis (channel layer)
                  └── X-Internal-Secret ──► Render (FastAPI :8001)
                                              ├── /agent/chat (non-streaming)
                                              ├── /agent/chat/stream (SSE)
                                              ├── /agent/document/index (RAG indexing)
                                              ├── /quiz/ (standalone quiz generation)
                                              └── /flashcards/ (standalone flashcard generation)
                                                  │
                                                  ├── Anthropic (Claude) ◄─ primary AI
                                                  ├── NVIDIA NIM ◄─ fallback
                                                  ├── Azure OpenAI ◄─ fallback
                                                  ├── DeepSeek ◄─ fallback
                                                  ├── OpenAI Embeddings ◄─ document RAG
                                                  └── Upstash Vector ◄─ vector store
```

## Local Development

**1. Django (API gateway, port 8000)**
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python run.py --port 8000 --reload
```

**2. FastAPI (AI service, port 8001)**
```bash
cd ai_service
pip install -r requirements.txt
python run.py
```

**3. React (frontend, port 5173)**
```bash
cd frontend
npm install
npm run dev
```


## Health Checks

- Django: `GET /health/`
- FastAPI: `GET /health`

## Key Design Rules

- **Django owns all DB work.** FastAPI never writes to the database.
- **FastAPI owns all AI work.** Django never builds prompts or calls LLMs.
- **Internal auth via shared secret.** All Django → FastAPI calls include `X-Internal-Secret`.
- **RAG is session-scoped.** Uploaded document chunks live in Upstash Vector under a `session_id` namespace. The session flag `has_document` tells FastAPI to inject the `search_document` tool.
- Use `docs/README.md` as the canonical documentation index.
