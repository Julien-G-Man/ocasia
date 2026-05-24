import json
import logging

from fastapi import APIRouter, HTTPException
from agent.registry import get_definitions
from agent.executor import execute_tool
from agent.schemas import (
    OrchestratorRequest, OrchestratorResponse, ToolCall, ToolResult,
)
from core.ai_client import ai_client

logger = logging.getLogger(__name__)

mcp_router = APIRouter()

_DEFAULT_SYSTEM = (
    "You are Lamla AI Tutor, a friendly educational assistant. "
    "Use tools for content fetching, quiz/flashcard generation, or answer evaluation. "
    "Do not call tools for simple Q&A. "
    "After tool results, synthesise them into a clear response."
)


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


@mcp_router.get("/tools")
async def list_tools(names: str | None = None):
    name_list = [n.strip() for n in names.split(",")] if names else None
    definitions = get_definitions(name_list)
    return {"count": len(definitions), "tools": [d.model_dump() for d in definitions]}


@mcp_router.post("/call", response_model=ToolResult)
async def call_tool(call: ToolCall):
    logger.info("[mcp:router] direct call tool=%s", call.name)
    result = await execute_tool(call)
    if result.error:
        raise HTTPException(status_code=400, detail=result.error)
    return result


@mcp_router.post("/orchestrate", response_model=OrchestratorResponse)
async def orchestrate(request: OrchestratorRequest):
    tool_defs = get_definitions(request.tools)
    anthropic_tools = [_to_anthropic_tool(d) for d in tool_defs]
    system = request.system_prompt or _DEFAULT_SYSTEM
    messages = list(request.messages)
    calls_made: list[str] = []
    iterations = 0
    logger.info("[mcp:router] orchestrate start tools=%d max_iter=%d messages=%d",
                len(anthropic_tools), request.max_iterations, len(messages))

    while iterations < request.max_iterations:
        iterations += 1
        try:
            result = await ai_client.generate_with_tools(
                messages=messages, tools=anthropic_tools,
                max_tokens=request.max_tokens, system=system, timeout=60,
            )
        except Exception as exc:
            logger.error("[mcp:router] generate_with_tools failed iter=%d: %s", iterations, exc)
            return OrchestratorResponse(response="", tool_calls_made=calls_made,
                                        iterations=iterations, error=f"AI provider error: {exc}")

        stop_reason = result.get("stop_reason", "end_turn")
        logger.debug("[mcp:router] iter=%d stop_reason=%s calls=%d",
                     iterations, stop_reason, len(result.get("tool_calls", [])))

        if stop_reason == "end_turn":
            text = result.get("text") or ""
            logger.info("[mcp:router] done iter=%d calls=%s len=%d", iterations, calls_made, len(text))
            return OrchestratorResponse(response=text, tool_calls_made=calls_made, iterations=iterations)

        tool_calls = result.get("tool_calls", [])
        if not tool_calls:
            logger.warning("[mcp:router] stop_reason=tool_use but no calls -- end_turn")
            return OrchestratorResponse(response=result.get("text") or "",
                                        tool_calls_made=calls_made, iterations=iterations)

        raw_content = _serialize_raw_content(result.get("raw_content", []))
        messages.append({"role": "assistant", "content": raw_content})

        tool_result_blocks = []
        for tc in tool_calls:
            tool_name = tc.get("name", "")
            calls_made.append(tool_name)
            logger.info("[mcp:router] calling tool=%s iter=%d", tool_name, iterations)
            call_obj = ToolCall(
                tool_use_id=tc.get("id", f"call_{tool_name}_{iterations}"),
                name=tool_name, input=tc.get("input", {}),
            )
            tool_result = await execute_tool(call_obj)
            if tool_result.error:
                content = f"[Tool error: {tool_result.error}]"
                logger.warning("[mcp:router] tool error tool=%s iter=%d: %s",
                               tool_name, iterations, tool_result.error)
            else:
                output = tool_result.output
                content = (json.dumps(output, ensure_ascii=False)
                           if isinstance(output, (dict, list)) else str(output))
                logger.info("[mcp:router] result tool=%s iter=%d len=%d ms=%.1f",
                            tool_name, iterations, len(content), tool_result.duration_ms)
            tool_result_blocks.append({
                "type": "tool_result",
                "tool_use_id": call_obj.tool_use_id,
                "content": content,
            })
        messages.append({"role": "user", "content": tool_result_blocks})

    logger.warning("[mcp:router] max_iterations=%d reached", request.max_iterations)
    return OrchestratorResponse(
        response="", tool_calls_made=calls_made, iterations=iterations,
        error=f"Stopped after {request.max_iterations} iterations without a final response.",
    )
