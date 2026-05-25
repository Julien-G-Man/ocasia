import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.chatbot.routes import chatbot_router
from services.quiz.routes import quiz_router
from services.flashcards.routes import flashcards_router
from agent.router import agent_router
from core.middleware import InternalAuthMiddleware
from core.config import settings

app = FastAPI(title="Lamla AI Engine")
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Protect internal endpoints with shared-secret auth middleware
app.add_middleware(InternalAuthMiddleware)

app.include_router(chatbot_router, prefix="/chatbot")
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
