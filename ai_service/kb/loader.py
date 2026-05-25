"""
KB store loader — resolves the knowledge file path and instantiates the active provider.

Path resolution order:
1. KB_FILE_PATH env var (explicit override)
2. {ai_service_root}/knowledge/text_embeddings.json  (production location)
3. {repo_root}/backend/apps/chatbot/platform_kb/text_embeddings.json  (local dev fallback)
"""

import logging
import os
from pathlib import Path

from kb.base import KBSearchProvider

logger = logging.getLogger(__name__)

_AI_SERVICE_ROOT = Path(__file__).resolve().parent.parent  # ai_service/


def _resolve_kb_file() -> Path:
    env_path = os.environ.get("KB_FILE_PATH", "")
    if env_path:
        return Path(env_path)

    candidate = _AI_SERVICE_ROOT / "platform_kb" / "text_embeddings.json"
    if candidate.exists():
        return candidate

    # Local dev: fall back to Django's copy
    django_fallback = _AI_SERVICE_ROOT.parent / "backend" / "apps" / "chatbot" / "platform_kb" / "text_embeddings.json"
    if django_fallback.exists():
        logger.info("[kb:loader] using Django KB fallback: %s", django_fallback)
        return django_fallback

    logger.warning("[kb:loader] knowledge file not found in any expected location")
    return candidate  # return the preferred path so error is clear


def _make_provider(kb_file: Path) -> KBSearchProvider:
    provider_name = os.environ.get("KB_SEARCH_PROVIDER", "tfidf").lower()
    if provider_name == "tfidf":
        from kb.tfidf_provider import TFIDFProvider
        return TFIDFProvider(kb_file)
    # openai / azure_openai — placeholder for when embeddings are wired up
    logger.warning("[kb:loader] unknown KB_SEARCH_PROVIDER=%r, falling back to tfidf", provider_name)
    from kb.tfidf_provider import TFIDFProvider
    return TFIDFProvider(kb_file)


kb_store: KBSearchProvider = _make_provider(_resolve_kb_file())
