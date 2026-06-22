import logging

_SILENT_PATHS = frozenset(["/warmup/", "/warmup", "/health", "/health/"])


class SilentPathsFilter(logging.Filter):
    """Drop uvicorn access log lines for health/warmup endpoints."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(p in msg for p in _SILENT_PATHS)
