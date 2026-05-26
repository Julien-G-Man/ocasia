import json
import logging

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
) -> tuple[str, str | None, dict]:
    """
    Run an agent loop. Returns (response_text, error_or_None, side_data).
    side_data carries out-of-band signals (e.g. action='show_quiz_form').
    Never raises — errors surface as the second tuple element.
    """
    tool_defs = get_definitions(tool_names)
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

