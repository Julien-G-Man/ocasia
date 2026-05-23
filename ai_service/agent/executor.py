"""
MCP Executor

Dispatches a ToolCall to its registered handler, enforces per-tool timeouts,
and records execution timing. All errors are caught here and returned as a
ToolResult with error set — the orchestrator loop never crashes on a bad tool.
"""

import asyncio
import inspect
import logging
import time

from agent.schemas import ToolCall, ToolResult
from agent.registry import get_handler, get_timeout

logger = logging.getLogger(__name__)


async def execute_tool(call: ToolCall) -> ToolResult:
    """
    Execute a single tool call and return a ToolResult.
    Never raises — all exceptions surface through ToolResult.error.
    """
    tool_name = call.name
    tool_input = call.input

    logger.info(
        "[mcp:executor] start tool=%s id=%s input_keys=%s",
        tool_name, call.tool_use_id, list(tool_input.keys()),
    )

    t0 = time.perf_counter()

    try:
        handler = get_handler(tool_name)
        timeout = get_timeout(tool_name)

        # Support both sync and async handlers
        if inspect.iscoroutinefunction(handler):
            coro = handler(**tool_input)
        else:
            coro = asyncio.to_thread(handler, **tool_input)

        output = await asyncio.wait_for(coro, timeout=timeout)

        duration_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "[mcp:executor] done tool=%s id=%s duration_ms=%.1f",
            tool_name, call.tool_use_id, duration_ms,
        )
        return ToolResult(
            tool_use_id=call.tool_use_id,
            name=tool_name,
            output=output,
            duration_ms=duration_ms,
        )

    except KeyError as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        logger.error("[mcp:executor] unknown tool=%s: %s", tool_name, exc)
        return ToolResult(tool_use_id=call.tool_use_id, name=tool_name,
                         error=f"Unknown tool '{tool_name}'.", duration_ms=duration_ms)

    except asyncio.TimeoutError:
        duration_ms = (time.perf_counter() - t0) * 1000
        timeout = get_timeout(tool_name)
        logger.warning("[mcp:executor] timeout tool=%s id=%s after %.1fs",
                       tool_name, call.tool_use_id, timeout)
        return ToolResult(tool_use_id=call.tool_use_id, name=tool_name,
                         error=f"Tool '{tool_name}' timed out after {timeout:.0f}s.",
                         duration_ms=duration_ms)

    except TypeError as exc:
        # Bad arguments from the AI
        duration_ms = (time.perf_counter() - t0) * 1000
        logger.warning("[mcp:executor] bad input tool=%s id=%s error=%s input=%s",
                       tool_name, call.tool_use_id, exc, tool_input)
        return ToolResult(tool_use_id=call.tool_use_id, name=tool_name,
                         error=f"Tool '{tool_name}' received unexpected arguments: {exc}",
                         duration_ms=duration_ms)

    except ValueError as exc:
        # Expected user-facing error (bad URL, transcript unavailable, etc.)
        duration_ms = (time.perf_counter() - t0) * 1000
        logger.warning("[mcp:executor] tool error tool=%s id=%s error=%s",
                       tool_name, call.tool_use_id, exc)
        return ToolResult(tool_use_id=call.tool_use_id, name=tool_name,
                         error=str(exc), duration_ms=duration_ms)

    except Exception as exc:
        # Unexpected failure — log full traceback
        duration_ms = (time.perf_counter() - t0) * 1000
        logger.exception("[mcp:executor] unexpected error tool=%s id=%s", tool_name, call.tool_use_id)
        return ToolResult(
            tool_use_id=call.tool_use_id,
            name=tool_name,
            error=f"Tool '{tool_name}' failed unexpectedly: {type(exc).__name__}: {exc}",
            duration_ms=duration_ms,
        )
