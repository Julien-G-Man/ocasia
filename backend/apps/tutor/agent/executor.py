"""Run individual LangChain tools with time limits and normalized errors."""

import asyncio
import json
import logging
import time

from apps.tutor.agent.registry import TOOL_TIMEOUTS

logger = logging.getLogger(__name__)


async def execute_tool(tool, arguments: dict) -> tuple[str, str | None, float]:
    started = time.perf_counter()
    try:
        output = await asyncio.wait_for(
            tool.ainvoke(arguments),
            timeout=TOOL_TIMEOUTS.get(tool.name, 30.0),
        )
        if isinstance(output, str):
            serialized = output
        else:
            serialized = json.dumps(output, ensure_ascii=False, default=str)
        return serialized, None, (time.perf_counter() - started) * 1000
    except asyncio.TimeoutError:
        error = f"Tool timed out after {TOOL_TIMEOUTS.get(tool.name, 30.0):g} seconds."
    except Exception as exc:
        error = str(exc) or exc.__class__.__name__
        logger.exception("Tutor tool %s failed", tool.name)
    return json.dumps({"error": error}), error, (time.perf_counter() - started) * 1000
