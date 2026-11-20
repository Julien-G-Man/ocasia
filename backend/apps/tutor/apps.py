import logging
import os
import sys

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class TutorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tutor"

    def ready(self):
        """Index bundled platform knowledge when a web worker starts."""
        command = os.path.basename(sys.argv[0]).casefold()
        args = [arg.casefold() for arg in sys.argv[1:]]
        is_runserver = "runserver" in args
        is_server = is_runserver or any(
            name in command or name in args
            for name in ("gunicorn", "uvicorn", "daphne")
        )
        if not is_server:
            return
        # Django's autoreloader imports the app in the parent and child.
        if is_runserver and os.environ.get("RUN_MAIN") != "true" and "--noreload" not in args:
            return

        try:
            from apps.tutor.retrieval import rag_engine

            indexed_count = rag_engine.index_platform_knowledge()
            logger.info("Platform knowledge startup indexing complete; %d source(s) indexed.", indexed_count)
        except Exception:
            # Keep the web worker alive, but make the failure visible. Retrieval
            # itself will return a structured error rather than indexing on demand.
            logger.exception("Could not index platform knowledge during tutor startup.")

