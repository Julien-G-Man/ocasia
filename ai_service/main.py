import logging
import logging.config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.quiz.routes import quiz_router
from services.flashcards.routes import flashcards_router
from agent.router import agent_router
from core.middleware import InternalAuthMiddleware
from core.config import settings

# ---------------------------------------------------------------------------
# Logging — INFO+ for all Lamla app code; keep noisy libraries quieter
# ---------------------------------------------------------------------------
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(levelname)s] %(name)s — %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "loggers": {
        # All Lamla service code
        "agent":    {"handlers": ["console"], "level": "INFO", "propagate": False},
        "services": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "core":     {"handlers": ["console"], "level": "INFO", "propagate": False},
        # Keep httpx / anthropic / openai SDK chatter quiet unless it errors
        "httpx":        {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "httpcore":     {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "anthropic":    {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "openai":       {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
})

app = FastAPI(title="Lamla AI Engine")
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(InternalAuthMiddleware)

app.include_router(quiz_router, prefix="/quiz")
app.include_router(flashcards_router, prefix="/flashcards")
app.include_router(agent_router, prefix="/agent")

logger.info("FastAPI CORS allowed origins: %s", settings.allowed_origins_list)


@app.get("/")
def check_root():
    return {"status": "ok", "message": "FastAPI Backend is live!"}


@app.get("/health")
def check_health():
    return {"status": "ok", "message": "Health check: FastAPI Backend is live!"}
