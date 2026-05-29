import json
import logging
from typing import AsyncGenerator

from core.ai_client import ai_client
from agent.executor import execute_tool
from agent.registry import get_definitions
from agent.schemas import ToolCall

logger = logging.getLogger(__name__)

def _to_anthropic_tool(definition) -> dict:
    return {"name": definition.name, "description": definition.description,
            "input_schema": definition.input_schema}


def _serialize_raw_content(raw_content: list) -> list:
    result = []
    for block in raw_content:
        if isinstance(block, dict):
            result.append(block)
        elif hasattr(block, "model_dump"):
            result.append(block.model_dump())
        elif hasattr(block, "__dict__"):
            d = {"type": getattr(block, "type", "text")}
            for attr in ("text", "id", "name", "input"):
                val = getattr(block, attr, None)
                if val is not None:
                    d[attr] = val
            result.append(d)
        else:
            result.append({"type": "text", "text": str(block)})
    return result


async def _run_agent_loop(
    messages: list[dict],
    system: str,
    tool_names: list[str],
    max_iterations: int,
    max_tokens: int,
    extra_tool_handlers: dict | None = None,
    extra_tool_defs: list | None = None,
) -> tuple[str, str | None, dict]:
    """
    Run an agent loop. Returns (response_text, error_or_None, side_data).
    side_data carries out-of-band signals (e.g. action='show_quiz_form').
    Never raises — errors surface as the second tuple element.

    extra_tool_handlers: {tool_name: async_callable(**input)} for per-request
                         tools (e.g. search_document with pre-bound session_id).
    extra_tool_defs: list[ToolDefinition] matching each extra handler.
    """
    tool_defs = get_definitions(tool_names)
    if extra_tool_defs:
        tool_defs = list(tool_defs) + list(extra_tool_defs)
    anthropic_tools = [_to_anthropic_tool(d) for d in tool_defs]
    msgs = list(messages)
    calls_made: list[str] = []
    side_data: dict = {}

    for iteration in range(1, max_iterations + 1):
        try:
            result = await ai_client.generate_with_tools(
                messages=msgs, tools=anthropic_tools,
                max_tokens=max_tokens, system=system, timeout=60,
            )
        except Exception as exc:
            logger.error("[agent] generate_with_tools failed iter=%d: %s", iteration, exc)
            return "", f"AI provider error: {exc}", side_data

        stop_reason = result.get("stop_reason", "end_turn")

        if stop_reason == "end_turn":
            text = result.get("text") or ""
            logger.info("[agent] done iter=%d calls=%s len=%d", iteration, calls_made, len(text))
            return text, None, side_data

        tool_calls = result.get("tool_calls", [])
        if not tool_calls:
            return result.get("text") or "", None, side_data

        raw_content = _serialize_raw_content(result.get("raw_content", []))
        msgs.append({"role": "assistant", "content": raw_content})

        tool_result_blocks = []
        for tc in tool_calls:
            tool_name = tc.get("name", "")
            calls_made.append(tool_name)
            call_obj = ToolCall(
                tool_use_id=tc.get("id", f"call_{tool_name}_{iteration}"),
                name=tool_name,
                input=tc.get("input", {}),
            )

            # Extra (per-request) handlers take priority over the global registry
            if extra_tool_handlers and tool_name in extra_tool_handlers:
                import time as _time
                _t = _time.monotonic()
                try:
                    output = await extra_tool_handlers[tool_name](**call_obj.input)
                    duration_ms = (_time.monotonic() - _t) * 1000
                    content = (json.dumps(output, ensure_ascii=False)
                               if isinstance(output, (dict, list)) else str(output))
                    logger.info("[agent] extra tool=%s iter=%d len=%d ms=%.1f",
                                tool_name, iteration, len(content), duration_ms)
                except Exception as exc:
                    content = f"[Tool error: {exc}]"
                    logger.warning("[agent] extra tool error tool=%s iter=%d: %s", tool_name, iteration, exc)
            else:
                tool_result = await execute_tool(call_obj)
                if tool_result.error:
                    content = f"[Tool error: {tool_result.error}]"
                    logger.warning("[agent] tool error tool=%s iter=%d: %s", tool_name, iteration, tool_result.error)
                else:
                    output = tool_result.output
                    content = (json.dumps(output, ensure_ascii=False)
                               if isinstance(output, (dict, list)) else str(output))
                    # Capture quiz form signal from no-op tool
                    if tool_name == "request_quiz_form" and isinstance(output, dict):
                        side_data["action"] = "show_quiz_form"
                        prefill_topic = output.get("topic", "")
                        if prefill_topic:
                            side_data["prefill"] = {"topic": prefill_topic}
                    logger.info("[agent] result tool=%s iter=%d len=%d ms=%.1f",
                                tool_name, iteration, len(content), tool_result.duration_ms)

            tool_result_blocks.append({
                "type": "tool_result",
                "tool_use_id": call_obj.tool_use_id,
                "content": content,
            })
        msgs.append({"role": "user", "content": tool_result_blocks})

    return "", f"Stopped after {max_iterations} iterations without a final response.", side_data


async def _run_agent_loop_stream(
    messages: list[dict],
    system: str,
    tool_names: list[str],
    max_iterations: int,
    max_tokens: int,
    extra_tool_handlers: dict | None = None,
    extra_tool_defs: list | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Streaming version of _run_agent_loop. Async generator.

    Yields typed event dicts consumed by the SSE router endpoint:
        {"type": "tool_start", "tool": name}    model invoked a tool (may arrive before execution)
        {"type": "tool_done",  "tool": name}    tool execution complete
        {"type": "token",      "content": str}  text delta from the final response
        {"type": "done",       "side_data": {}} streaming complete; side_data carries action/prefill
        {"type": "error",      "message": str}  unrecoverable error

    Never raises — errors are surfaced as "error" events.

    extra_tool_handlers: {tool_name: async_callable(**input)} for per-request
                         tools (e.g. search_document with pre-bound session_id).
    extra_tool_defs: list[ToolDefinition] matching each extra handler.
    """
    tool_defs = get_definitions(tool_names)
    if extra_tool_defs:
        tool_defs = list(tool_defs) + list(extra_tool_defs)
    anthropic_tools = [_to_anthropic_tool(d) for d in tool_defs]
    msgs = list(messages)
    side_data: dict = {}

    for iteration in range(1, max_iterations + 1):
        tool_calls_this_iter: list[dict] = []
        raw_content_blocks: list = []
        stop_reason = "end_turn"
        error_msg: str | None = None

        try:
            async for event in ai_client.generate_with_tools_stream(
                messages=msgs, tools=anthropic_tools,
                max_tokens=max_tokens, system=system, timeout=60,
            ):
                etype = event.get("type")

                if etype == "tool_start":
                    yield event          # forward to client immediately

                elif etype == "token":
                    yield event          # forward text delta to client

                elif etype == "_result":
                    stop_reason = event.get("stop_reason", "end_turn")
                    tool_calls_this_iter = event.get("tool_calls", [])
                    raw_content_blocks = event.get("raw_content", [])
                    error_msg = event.get("error")

        except Exception as exc:
            logger.error("[agent:stream] generate_with_tools_stream failed iter=%d: %s", iteration, exc)
            yield {"type": "error", "message": f"AI provider error: {exc}"}
            return

        if error_msg:
            yield {"type": "error", "message": error_msg}
            return

        if stop_reason == "end_turn":
            logger.info("[agent:stream] done iter=%d", iteration)
            yield {"type": "done", "side_data": side_data}
            return

        # Tool execution phase
        if not tool_calls_this_iter:
            yield {"type": "done", "side_data": side_data}
            return

        raw_content = _serialize_raw_content(raw_content_blocks)
        msgs.append({"role": "assistant", "content": raw_content})

        tool_result_blocks = []
        for tc in tool_calls_this_iter:
            tool_name = tc.get("name", "")
            call_obj = ToolCall(
                tool_use_id=tc.get("id", f"call_{tool_name}_{iteration}"),
                name=tool_name,
                input=tc.get("input", {}),
            )

            # Extra (per-request) handlers take priority over the global registry
            if extra_tool_handlers and tool_name in extra_tool_handlers:
                import time as _time
                _t = _time.monotonic()
                try:
                    output = await extra_tool_handlers[tool_name](**call_obj.input)
                    duration_ms = (_time.monotonic() - _t) * 1000
                    content = (json.dumps(output, ensure_ascii=False)
                               if isinstance(output, (dict, list)) else str(output))
                    logger.info("[agent:stream] extra tool=%s iter=%d len=%d ms=%.1f",
                                tool_name, iteration, len(content), duration_ms)
                except Exception as exc:
                    content = f"[Tool error: {exc}]"
                    logger.warning("[agent:stream] extra tool error tool=%s iter=%d: %s",
                                   tool_name, iteration, exc)
            else:
                tool_result = await execute_tool(call_obj)
                if tool_result.error:
                    content = f"[Tool error: {tool_result.error}]"
                    logger.warning(
                        "[agent:stream] tool error tool=%s iter=%d: %s",
                        tool_name, iteration, tool_result.error,
                    )
                else:
                    output = tool_result.output
                    content = (
                        json.dumps(output, ensure_ascii=False)
                        if isinstance(output, (dict, list)) else str(output)
                    )
                    if tool_name == "request_quiz_form" and isinstance(output, dict):
                        side_data["action"] = "show_quiz_form"
                        prefill_topic = output.get("topic", "")
                        if prefill_topic:
                            side_data["prefill"] = {"topic": prefill_topic}
                    logger.info(
                        "[agent:stream] tool=%s iter=%d done ms=%.1f",
                        tool_name, iteration, tool_result.duration_ms,
                    )

            yield {"type": "tool_done", "tool": tool_name}
            tool_result_blocks.append({
                "type": "tool_result",
                "tool_use_id": call_obj.tool_use_id,
                "content": content,
            })

        msgs.append({"role": "user", "content": tool_result_blocks})

    yield {"type": "error", "message": f"Stopped after {max_iterations} iterations without a final response."}

