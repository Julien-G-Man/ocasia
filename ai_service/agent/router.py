import json
import logging

from fastapi import APIRouter, HTTPException
from agent.executor import execute_tool
from agent.prompts import ORCHESTRATE_SYSTEM, build_chat_system_prompt, wrap_file_context
from agent.registry import get_definitions
from agent.schemas import OrchestratorRequest, OrchestratorResponse, ToolCall, ToolResult, ChatRequest
from core.ai_client import ai_client

logger = logging.getLogger(__name__)

agent_router = APIRouter()

_CHAT_TOOLS = ["kb_search", "web_search"]
_CHAT_MAX_ITERATIONS = 5
_CHAT_MAX_TOKENS = 1200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
) -> tuple[str, str | None]:
    """
    Run an agent loop. Returns (response_text, error_or_None).
    Never raises — errors surface as the second tuple element.
    """
    tool_defs = get_definitions(tool_names)
    anthropic_tools = [_to_anthropic_tool(d) for d in tool_defs]
    msgs = list(messages)
    calls_made: list[str] = []

    for iteration in range(1, max_iterations + 1):
        try:
            result = await ai_client.generate_with_tools(
                messages=msgs, tools=anthropic_tools,
                max_tokens=max_tokens, system=system, timeout=60,
            )
        except Exception as exc:
            logger.error("[agent] generate_with_tools failed iter=%d: %s", iteration, exc)
            return "", f"AI provider error: {exc}"

        stop_reason = result.get("stop_reason", "end_turn")

        if stop_reason == "end_turn":
            text = result.get("text") or ""
            logger.info("[agent] done iter=%d calls=%s len=%d", iteration, calls_made, len(text))
            return text, None

        tool_calls = result.get("tool_calls", [])
        if not tool_calls:
            return result.get("text") or "", None

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
                logger.info("[agent] result tool=%s iter=%d len=%d ms=%.1f",
                            tool_name, iteration, len(content), tool_result.duration_ms)
            tool_result_blocks.append({
                "type": "tool_result",
                "tool_use_id": call_obj.tool_use_id,
                "content": content,
            })
        msgs.append({"role": "user", "content": tool_result_blocks})

    return "", f"Stopped after {max_iterations} iterations without a final response."


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@agent_router.get("/tools")
async def list_tools(names: str | None = None):
    name_list = [n.strip() for n in names.split(",")] if names else None
    definitions = get_definitions(name_list)
    return {"count": len(definitions), "tools": [d.model_dump() for d in definitions]}


@agent_router.post("/call", response_model=ToolResult)
async def call_tool(call: ToolCall):
    logger.info("[agent:router] direct call tool=%s", call.name)
    result = await execute_tool(call)
    if result.error:
        raise HTTPException(status_code=400, detail=result.error)
    return result


@agent_router.post("/orchestrate", response_model=OrchestratorResponse)
async def orchestrate(request: OrchestratorRequest):
    tool_defs = get_definitions(request.tools)
    anthropic_tools = [_to_anthropic_tool(d) for d in tool_defs]
    system = request.system_prompt or ORCHESTRATE_SYSTEM
    messages = list(request.messages)
    calls_made: list[str] = []
    iterations = 0
    logger.info("[agent:router] orchestrate start tools=%d max_iter=%d messages=%d",
                len(anthropic_tools), request.max_iterations, len(messages))

    while iterations < request.max_iterations:
        iterations += 1
        try:
            result = await ai_client.generate_with_tools(
                messages=messages, tools=anthropic_tools,
                max_tokens=request.max_tokens, system=system, timeout=60,
            )
        except Exception as exc:
            logger.error("[agent:router] generate_with_tools failed iter=%d: %s", iterations, exc)
            return OrchestratorResponse(response="", tool_calls_made=calls_made,
                                        iterations=iterations, error=f"AI provider error: {exc}")

        stop_reason = result.get("stop_reason", "end_turn")
        logger.debug("[agent:router] iter=%d stop_reason=%s calls=%d",
                     iterations, stop_reason, len(result.get("tool_calls", [])))

        if stop_reason == "end_turn":
            text = result.get("text") or ""
            logger.info("[agent:router] done iter=%d calls=%s len=%d", iterations, calls_made, len(text))
            return OrchestratorResponse(response=text, tool_calls_made=calls_made, iterations=iterations)

        tool_calls = result.get("tool_calls", [])
        if not tool_calls:
            logger.warning("[agent:router] stop_reason=tool_use but no calls -- end_turn")
            return OrchestratorResponse(response=result.get("text") or "",
                                        tool_calls_made=calls_made, iterations=iterations)

        raw_content = _serialize_raw_content(result.get("raw_content", []))
        messages.append({"role": "assistant", "content": raw_content})

        tool_result_blocks = []
        for tc in tool_calls:
            tool_name = tc.get("name", "")
            calls_made.append(tool_name)
            logger.info("[agent:router] calling tool=%s iter=%d", tool_name, iterations)
            call_obj = ToolCall(
                tool_use_id=tc.get("id", f"call_{tool_name}_{iterations}"),
                name=tool_name, input=tc.get("input", {}),
            )
            tool_result = await execute_tool(call_obj)
            if tool_result.error:
                content = f"[Tool error: {tool_result.error}]"
                logger.warning("[agent:router] tool error tool=%s iter=%d: %s",
                               tool_name, iterations, tool_result.error)
            else:
                output = tool_result.output
                content = (json.dumps(output, ensure_ascii=False)
                           if isinstance(output, (dict, list)) else str(output))
                logger.info("[agent:router] result tool=%s iter=%d len=%d ms=%.1f",
                            tool_name, iterations, len(content), tool_result.duration_ms)
            tool_result_blocks.append({
                "type": "tool_result",
                "tool_use_id": call_obj.tool_use_id,
                "content": content,
            })
        messages.append({"role": "user", "content": tool_result_blocks})

    logger.warning("[agent:router] max_iterations=%d reached", request.max_iterations)
    return OrchestratorResponse(
        response="", tool_calls_made=calls_made, iterations=iterations,
        error=f"Stopped after {request.max_iterations} iterations without a final response.",
    )


@agent_router.post("/chat")
async def agent_chat(request: ChatRequest):
    system = build_chat_system_prompt(request.tutor_mode, request.user_stats)

    messages: list[dict] = []
    for msg in request.conversation_history:
        role = "user" if msg.get("message_type") == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})

    user_content = (
        wrap_file_context(request.file_text, request.message)
        if request.file_text else request.message
    )
    messages.append({"role": "user", "content": user_content})

    logger.info(
        "[agent:chat] start mode=%s stats=%s file=%s history=%d",
        request.tutor_mode,
        "yes" if request.user_stats else "no",
        "yes" if request.file_text else "no",
        len(request.conversation_history),
    )

    response_text, agent_error = await _run_agent_loop(
        messages=messages,
        system=system,
        tool_names=_CHAT_TOOLS,
        max_iterations=_CHAT_MAX_ITERATIONS,
        max_tokens=_CHAT_MAX_TOKENS,
    )

    if not response_text:
        logger.warning("[agent:chat] agent empty/failed (%s) — one-shot fallback", agent_error)
        try:
            from core.http import get_async_client
            client = await get_async_client()
            raw = await ai_client.generate_content(
                client=client,
                prompt=f"{system}\n\nStudent: {request.message}\n\nAI Tutor:",
                max_tokens=_CHAT_MAX_TOKENS,
                timeout=60,
            )
            response_text = raw if isinstance(raw, str) else str(raw)
        except Exception as exc:
            logger.exception("[agent:chat] one-shot fallback failed: %s", exc)
            raise HTTPException(status_code=503, detail="AI service error")

    if not response_text:
        raise HTTPException(status_code=503, detail="AI service returned an empty response")

    return {"response": response_text}
