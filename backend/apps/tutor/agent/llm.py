"""Chat model factory shared by the tutor agent and its tools."""

from functools import lru_cache
from django.conf import settings


@lru_cache(maxsize=1)
def build_chat_model():
    """LangChain chat model used by the tutor agent and its tools."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError(
            "LangChain OpenAI integration is missing. Install langchain-openai."
        ) from exc

    api_key = getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be configured for the tutor model.")

    return ChatOpenAI(
        api_key=api_key,
        model=getattr(settings, "TUTOR_MODEL", "gpt-4o-mini"),
        temperature=getattr(settings, "TUTOR_TEMPERATURE", 0.3),
        max_tokens=getattr(settings, "CHATBOT_MAX_TOKENS", 1200),
    )