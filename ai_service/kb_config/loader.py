"""
KB store loader — resolves the platform_kb directory and instantiates the active provider.

Path resolution order:
1. KB_FILE_PATH env var (must point to a directory containing kb_index.json + .md files)
2. {ai_service_root}/platform_kb/  (default)
"""

import logging
import os
from pathlib import Path

from kb_config.base import KBSearchProvider

logger = logging.getLogger(__name__)

_AI_SERVICE_ROOT = Path(__file__).resolve().parent.parent  # ai_service/


def _resolve_kb_path() -> Path:
    env_path = os.environ.get("KB_FILE_PATH", "")
    if env_path:
        return Path(env_path)
    return _AI_SERVICE_ROOT / "platform_kb"


def _make_provider(kb_path: Path) -> KBSearchProvider:
    from kb_config.tfidf_provider import TFIDFProvider

    provider_name = os.environ.get("KB_SEARCH_PROVIDER", "tfidf").lower()
    if provider_name != "tfidf":
        logger.warning("[kb] unknown KB_SEARCH_PROVIDER=%r, falling back to tfidf", provider_name)
    return TFIDFProvider(kb_path)


kb_store: KBSearchProvider = _make_provider(_resolve_kb_path())
