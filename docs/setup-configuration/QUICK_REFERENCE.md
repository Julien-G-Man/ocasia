# Quick Reference

## Critical Environment Variables

Django (`backend/.env`):

- `SECRET_KEY`
- `DEBUG`
- `FASTAPI_BASE_URL`
- `FASTAPI_SECRET`
- `CORS_ALLOWED_ORIGINS`
- `CSRF_TRUSTED_ORIGINS`
- `ADMIN_EMAIL`
- `GOOGLE_OAUTH_CLIENT_ID` - **Google OAuth client ID (required for Google Sign-In)**
- `GOOGLE_OAUTH_CLIENT_SECRET` - Google OAuth secret (not used in current token-exchange flow)
- `STORAGE_BACKEND` (`local` or `cloudinary`)
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` (if Cloudinary is enabled)
- `PAYSTACK_PUBLIC_KEY` — Paystack public key (`pk_test_...` / `pk_live_...`)
- `PAYSTACK_SECRET_KEY` — Paystack secret key, backend only, never expose to frontend

FastAPI (`ai_service/.env` or process env):

- `FASTAPI_SECRET`
- `FASTAPI_ALLOWED_ORIGINS`
- `AI_PROVIDER_ORDER` — comma-separated list of providers, e.g. `claude,nvidia_deepseek` (default: `nvidia_deepseek,nvidia_openai,claude`)
- Claude: `CLAUDE_API_KEY` (**required to use Claude**), `CLAUDE_MODEL` (default: `claude-opus-4-6`)
- NVIDIA DeepSeek: `NVIDIA_DEEPSEEK_API_KEY`, `NVIDIA_DEEPSEEK_MODEL`, `NVIDIA_DEEPSEEK_THINKING`
- NVIDIA OpenAI: `NVIDIA_OPENAI_API_KEY`, `NVIDIA_OPENAI_MODEL`
- Azure OpenAI: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`
- DeepSeek: `DEEPSEEK_API_KEY`, `DEEPSEEK_API_URL`
- Gemini: `GEMINI_API_KEY`, `GEMINI_API_URL`
- HuggingFace: `HUGGING_FACE_API_TOKEN`, `HUGGING_FACE_MODEL`
- `SEARCH_API_KEY` (or `TAVILY_API_KEY`) — Tavily web search key used by the `search_web` agent tool
- `KB_SEARCH_PROVIDER` — KB retrieval backend: `tfidf` (default, no cost) or `openai`
- `KB_FILE_PATH` — override path to the `platform_kb/` directory (optional; auto-resolved if unset)

See `docs/architecture-design/AI_PROVIDERS.md` for full provider docs.

Frontend (`frontend/.env`):

- `REACT_APP_DJANGO_API_URL`
- `REACT_APP_FASTAPI_URL`
- `REACT_APP_GOOGLE_CLIENT_ID` - **Google OAuth client ID (must match backend)**
- `REACT_APP_EMAILJS_PUBLIC_KEY` - EmailJS account public key
- `REACT_APP_EMAILJS_SERVICE_ID` - EmailJS email service ID
- `REACT_APP_EMAILJS_TEMPLATE_VERIFY` - EmailJS template ID for verification emails
- `REACT_APP_EMAILJS_TEMPLATE_RESET` - EmailJS template ID for password reset emails

## High-Use APIs

Auth:

- `POST /api/auth/signup/` - Create account with email/password
- `POST /api/auth/login/` - Login with email/username and password
- `POST /api/auth/google/` - **Sign in/up with Google OAuth**
- `POST /api/auth/logout/` - Invalidate token
- `GET /api/auth/me/` - Get current user info

Quiz:

- `POST /api/quiz/ajax-extract-text/`
- `POST /api/quiz/generate/`
- `POST /api/quiz/submit/`
- `GET /api/quiz/history/`

Flashcards:

- `POST /api/flashcards/ajax-extract-text/`
- `POST /api/flashcards/generate/`
- `POST /api/flashcards/save/`
- `GET /api/flashcards/decks/`
- `POST /api/flashcards/review/`

Chat:

- `POST /api/chat/`
- `POST /api/chat/file/`
- `GET /api/chat/history/`
- `DELETE /api/chat/history/clear/`
- `POST /api/chat/history/rename/`

Materials:

- `GET /api/materials/`
- `GET /api/materials/mine/`
- `POST /api/materials/upload/`
- `POST /api/materials/:id/download/`
- `POST /api/materials/:id/extract/`
- `DELETE /api/materials/:id/delete/`

Donations:

- `POST /api/subscriptions/donate/initiate/` - Start a Paystack donation (anon or authenticated)
- `GET /api/subscriptions/donate/verify/?reference=xxx` - Verify payment after redirect
- `POST /api/subscriptions/webhook/` - Paystack webhook (signature-verified)

Dashboard/Admin:

- `GET /api/dashboard/stats/`
- `POST /api/dashboard/contact/`
- `POST /api/dashboard/newsletter/`
- `GET /api/dashboard/admin/stats/`
- `GET /api/dashboard/admin/usage-trends/`
- `GET /api/dashboard/admin/activity/`
- `GET /api/dashboard/admin/anonymous-usage/`
- `GET /api/dashboard/admin/users/`
- `DELETE /api/dashboard/admin/users/:id/`
- `GET /api/dashboard/admin/settings/`
- `PUT /api/dashboard/admin/settings/`

## Important Behavior

- FastAPI `/health` is public for probes.
- Non-health FastAPI routes require `X-Internal-Secret` from Django.
- React warmup pings run on load and every 10 minutes.
- Materials extraction/download can use Cloudinary signed URL fallback when raw asset URLs are restricted.
