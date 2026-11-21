"""AI latency recording."""

import logging

from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


async def record_ai_latency(feature: str, duration_ms: int) -> None:
    try:
        from apps.dashboard.models import AIResponseLatency

        await sync_to_async(AIResponseLatency.objects.create)(
            feature=feature, duration_ms=duration_ms
        )
    except Exception:
        pass
