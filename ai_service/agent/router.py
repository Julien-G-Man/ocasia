import json
import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from agent.executor import execute_tool
from agent.prompts import ORCHESTRATE_SYSTEM, build_chat_system_prompt, wrap_file_context
from agent.registry import get_definitions, _generate_quiz_handler
from agent.helpers import _to_anthropic_tool, _serialize_raw_content, _run_agent_loop, _run_agent_loop_stream
from agent.schemas import (
    OrchestratorRequest, OrchestratorResponse, ToolCall, ToolResult,
    ChatRequest, AgentQuizGenerateRequest, IndexDocumentRequest,
)
from core.ai_client import ai_client

logger = logging.getLogger(__name__)

agent_router = APIRouter()

_CHAT_TOOLS = ["kb_search", "search_web", "request_quiz_form"]
_CHAT_MAX_ITERATIONS = 5
_CHAT_MAX_TOKENS = 1200


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

    # Inject search_document tool when this session has a document indexed.
    # Only via extra_defs — NOT added to tool_names, which would cause the
    # registry to include it AND extra_defs to add it again → duplicate error.
    extra_handlers: dict | None = None
    extra_defs: list | None = None
    if request.has_document and request.session_id:
        from agent.tools.document import make_search_document_handler
        from agent.registry import TOOL_REGISTRY
        extra_handlers = {"search_document": make_search_document_handler(request.session_id)}
        extra_defs = [TOOL_REGISTRY["search_document"]["definition"]]

    logger.info(
        "[agent:chat] start mode=%s stats=%s file=%s doc=%s history=%d",
        request.tutor_mode,
        "yes" if request.user_stats else "no",
        "yes" if request.file_text else "no",
        "yes" if request.has_document else "no",
        len(request.conversation_history),
    )

    response_text, agent_error, side_data = await _run_agent_loop(
        messages=messages,
        system=system,
        tool_names=_CHAT_TOOLS,
        max_iterations=_CHAT_MAX_ITERATIONS,
        max_tokens=_CHAT_MAX_TOKENS,
        extra_tool_handlers=extra_handlers,
        extra_tool_defs=extra_defs,
    )

    if not response_text:
        logger.warning("[agent:chat] agent empty/failed (%s) — one-shot fallback", agent_error)
        side_data = {}  # side_data is irrelevant if the loop failed
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

    result: dict = {"response": response_text}
    if side_data.get("action"):
        result["action"] = side_data["action"]
    if side_data.get("prefill"):
        result["prefill"] = side_data["prefill"]
    return result


@agent_router.post("/chat/stream")
async def agent_chat_stream(request: ChatRequest):
    """
    SSE streaming version of /agent/chat.

    Streams typed events as they occur:
      tool_start  — model invoked a tool
      tool_done   — tool execution complete
      token       — text delta from the final response
      done        — streaming complete (carries side_data with action/prefill)
      error       — unrecoverable failure

    The Django proxy buffers all token events, concatenates them, and saves the
    full text to the database on the "done" event.
    """
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

    # Inject search_document tool when this session has a document indexed.
    # Only via extra_defs — NOT added to stream_tool_names for the same reason.
    stream_extra_handlers: dict | None = None
    stream_extra_defs: list | None = None
    if request.has_document and request.session_id:
        from agent.tools.document import make_search_document_handler
        from agent.registry import TOOL_REGISTRY
        stream_extra_handlers = {"search_document": make_search_document_handler(request.session_id)}
        stream_extra_defs = [TOOL_REGISTRY["search_document"]["definition"]]

    logger.info(
        "[agent:chat:stream] start mode=%s stats=%s file=%s doc=%s history=%d",
        request.tutor_mode,
        "yes" if request.user_stats else "no",
        "yes" if request.file_text else "no",
        "yes" if request.has_document else "no",
        len(request.conversation_history),
    )

    async def event_generator():
        try:
            async for event in _run_agent_loop_stream(
                messages=messages,
                system=system,
                tool_names=_CHAT_TOOLS,
                max_iterations=_CHAT_MAX_ITERATIONS,
                max_tokens=_CHAT_MAX_TOKENS,
                extra_tool_handlers=stream_extra_handlers,
                extra_tool_defs=stream_extra_defs,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            logger.exception("[agent:chat:stream] unhandled error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Internal server error'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


# ---------------------------------------------------------------------------
# Quiz generation endpoint (bypasses the conversational loop)
# ---------------------------------------------------------------------------

def _determine_difficulty(user_stats: dict | None, topic: str) -> str:
    """Auto-determine quiz difficulty from user performance stats."""
    if not user_stats:
        return "medium"
    topic_lower = topic.lower()
    for item in user_stats.get("all_topics", []):
        if isinstance(item, (list, tuple)) and item:
            t = str(item[0]).lower()
            if t in topic_lower or topic_lower in t:
                acc = float(item[1]) if len(item) > 1 else 50
                if acc < 60:
                    return "hard"   # struggling — give harder practice
                if acc < 80:
                    return "medium"
                return "hard"       # already strong — challenge them further
    avg = float(user_stats.get("avg_score", 0) or 0)
    if avg >= 80:
        return "hard"
    if avg >= 60:
        return "medium"
    return "easy"


@agent_router.post("/quiz/generate/")
async def generate_quiz_for_chat(request: AgentQuizGenerateRequest):
    """
    Standalone quiz generation — called by the Django proxy after the user fills
    the inline quiz-param card. No conversational context, no agent loop.
    """
    difficulty = _determine_difficulty(request.user_stats, request.topic)
    study_text = f"Topic: {request.topic}\n\nGenerate questions based on expert knowledge of this subject."

    logger.info(
        "[agent:quiz/generate] topic=%r difficulty=%s num_questions=%d",
        request.topic, difficulty, request.num_questions,
    )

    try:
        quiz_data = await _generate_quiz_handler(
            study_text=study_text,
            subject=request.topic,
            difficulty=difficulty,
            num_mcq=request.num_questions,
            num_short=0,
        )
    except Exception as exc:
        logger.exception("[agent:quiz/generate] generation failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Quiz generation failed: {exc}")

    quiz_data["id"] = f"agent-{uuid.uuid4().hex[:8]}"
    quiz_data["time_limit"] = request.time_limit
    return {"quiz_data": quiz_data}


# ---------------------------------------------------------------------------
# Document indexing endpoint (RAG)
# ---------------------------------------------------------------------------

@agent_router.post("/document/index")
async def index_document(request: IndexDocumentRequest):
    """
    Embed and store document chunks in Upstash Vector for a chat session.
    Called fire-and-forget by Django after file extraction.
    """
    if not request.chunks:
        return {"indexed": 0, "session_id": request.session_id}

    logger.info(
        "[agent:document/index] session=%s chunks=%d file=%r",
        request.session_id, len(request.chunks), request.filename,
    )

    try:
        from core.upstash import upsert_document_chunks
        count = await upsert_document_chunks(
            session_id=request.session_id,
            chunks=request.chunks,
            filename=request.filename,
        )
        return {"indexed": count, "session_id": request.session_id}
    except Exception as exc:
        logger.exception("[agent:document/index] failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Document indexing failed: {exc}")
