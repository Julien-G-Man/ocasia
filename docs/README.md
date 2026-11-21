# Ocasia Documentation

This folder is the maintained source of truth for architecture, setup, features, security, and deployment.

## Read In This Order

1. `setup-configuration/GETTING_STARTED.md`
2. `setup-configuration/QUICK_REFERENCE.md`
3. `architecture-design/ARCHITECTURE.md`
4. `frontend/ROUTES_AND_PAGES.md`

## Core Docs

- `architecture-design/ARCHITECTURE.md` - system components and request flow
- `architecture-design/AGENT_IMPLEMENTATION.md` - tutor agent loop, tool catalog, prompts, and safety rules
- `architecture-design/GRAPHIFY.md` - generated repo graph snapshot and Mermaid system map
- `architecture-design/AI_PROVIDERS.md` - multi-provider AI orchestrator, Claude integration, and all env vars
- `architecture-design/FRONTEND_INTEGRATION.md` - React to Django tutor contracts
- `architecture-design/TUTOR_RAG_PGVECTOR.md` - tutor document indexing and pgvector retrieval
- `setup-configuration/GETTING_STARTED.md` - local environment setup
- `setup-configuration/QUICK_REFERENCE.md` - high-signal env vars and common endpoints
- `setup-configuration/AUTHENTICATION_SETUP.md` - auth integration setup (password + Google OAuth)
- `authentication/CUSTOM_USER_MODEL.md` - user model behavior and admin flag
- `authentication/EMAIL_VERIFICATION.md` - verification flow and API
- `authentication/PASSWORD_RESET.md` - password reset flow, API contracts, and frontend build guide
- `authentication/GOOGLE_OAUTH.md` - **Google OAuth 2.0 integration guide (setup, testing, security)**
- `features/QUIZ.md` - quiz generation and quiz lifecycle
- `features/FLASHCARDS.md` - flashcards feature and API behavior
- `features/TUTOR.md` - AI tutor feature (chat, tools, streaming, RAG)
- `frontend/ROUTES_AND_PAGES.md` - current route ownership and aliases
- `deployment-guides/DEPLOYMENT_CHECKLIST.md` - deploy preflight checklist
- `deployment-guides/RENDER_DEPLOYMENT_GUIDE.md` - backend deployment specifics
- `deployment-guides/VERCEL_FRONTEND_DEPLOYMENT.md` - frontend deployment specifics
- `security-reference/SECURITY.md` - security controls and rules

## Payments & Strategy

- `payments-strategy/PAYMENTS_AND_SUBSCRIPTIONS.md` - Paystack integration, voluntary donations (Phase 1), freemium subscription model (Phase 2), go-live checklist, and guiding principles
- `roadmap/OVERVIEW.md` - Intelligent edtech feature roadmap and build sequence
- `roadmap/TIER1_LOW_COST_HIGH_IMPACT.md` - Weak areas, spaced quiz scheduling, daily plan, badges, digest emails, exam mode
- `roadmap/TIER2_MODERATE_LLM.md` - Mistake analysis, material summariser, Socratic tutor, weekly AI patterns
- `roadmap/TIER3_ARCHITECTURE.md` - Celery queue, LLM budget, concept tagging, content intelligence
- `roadmap/TIER4_SOCIAL_COMMUNITY.md` - Study groups, peer challenges, material ratings, community health

## Documentation Rules

- Keep docs aligned with code changes in the same PR.
- Remove temporary migration notes and one-off status reports.
- Prefer one canonical doc per topic; avoid near-duplicates.
- All Django API routes are rooted at `/api/` unless noted otherwise.
