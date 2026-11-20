"""Tool-calling tutor loop implemented with LangChain messages and tools."""

import logging
from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from apps.tutor.agent.executor import execute_tool
from apps.tutor.agent.prompts import build_tutor_system_prompt, wrap_file_context
from apps.tutor.agent.registry import get_tools
from apps.tutor.agent.schemas import TutorAgentResult
from apps.tutor.services import build_chat_model

logger = logging.getLogger(__name__)

MAX_AGENT_ITERATIONS = 10


def _message_content(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "") for item in content if isinstance(item, dict)
        ).strip()
    return str(content or "").strip()


async def run_tutor_agent(
    message: str,
    history=(),
    *,
    tutor_mode: str = "direct",
    user_stats: dict | None = None,
    file_text: str | None = None,
    session_id: str | None = None,
    has_document: bool = False,
) -> TutorAgentResult:
    if not message or not message.strip():
        raise ValueError("message must not be empty")

    system = build_tutor_system_prompt(tutor_mode=tutor_mode, user_stats=user_stats)
    messages = [SystemMessage(content=system)]
    for item in history:
        role = item.get("message_type") or item.get("role")
        content = (item.get("content") or "").strip()
        if not content:
            continue
        if role in {"user", "human"}:
            messages.append(HumanMessage(content=content))
        elif role in {"ai", "assistant", "tutor"}:
            messages.append(AIMessage(content=content))

    latest_content = wrap_file_context(file_text, message) if file_text else message.strip()
    messages.append(HumanMessage(content=latest_content))

    tools = get_tools()
    tools_by_name = {tool.name: tool for tool in tools}
    model = build_chat_model().bind_tools(tools)
    tool_calls_made: list[str] = []
    action = None
    prefill = None

    for iteration in range(1, MAX_AGENT_ITERATIONS + 1):
        result = await model.ainvoke(messages)
        if not isinstance(result, AIMessage):
            raise RuntimeError("Tutor model returned an unexpected message type.")
        calls = result.tool_calls or []
        if not calls:
            response = _message_content(result.content)
            if not response:
                raise RuntimeError("Tutor model returned an empty response.")
            return TutorAgentResult(
                response=response,
                tool_calls_made=tool_calls_made,
                action=action,
                prefill=prefill,
            )

        messages.append(result)
        for call in calls:
            name = call.get("name", "")
            tool_calls_made.append(name)
            tool = tools_by_name.get(name)
            if tool is None:
                output = '{"error":"Unknown tool."}'
                error = "Unknown tool."
            else:
                tool_args = call.get("args") or {}
                if name == "search_document":
                    tool_args["session_id"] = session_id
                output, error, duration_ms = await execute_tool(tool, tool_args)
                logger.info("Tutor tool %s completed in %.1fms (error=%s)", name, duration_ms, bool(error))

            if name == "request_quiz_form" and not error:
                try:
                    import json
                    topic = json.loads(output).get("topic", "")
                    action = "show_quiz_form"
                    if topic:
                        prefill = {"topic": topic}
                except (TypeError, ValueError):
                    pass

            messages.append(ToolMessage(content=output, tool_call_id=call.get("id", name)))

    logger.warning("Tutor agent reached the %d-iteration limit", MAX_AGENT_ITERATIONS)
    final = await build_chat_model().ainvoke(
        messages + [HumanMessage(content="Give the student the best concise answer using the tool results above. Do not call more tools.")]
    )
    response = _message_content(final.content)
    if not response:
        raise RuntimeError("Tutor agent stopped before producing a final response.")
    return TutorAgentResult(
        response=response,
        tool_calls_made=tool_calls_made,
        action=action,
        prefill=prefill,
    )


async def stream_tutor_agent(
    message: str,
    history=(),
    *,
    tutor_mode: str = "direct",
    user_stats: dict | None = None,
    file_text: str | None = None,
    session_id: str | None = None,
    has_document: bool = False,
) -> AsyncIterator[dict]:
    """Stream tool lifecycle and final response tokens from the tutor agent."""
    if not message or not message.strip():
        yield {"type": "error", "message": "message must not be empty"}
        return

    messages = [SystemMessage(content=build_tutor_system_prompt(tutor_mode, user_stats))]
    for item in history:
        role = item.get("message_type") or item.get("role")
        content = (item.get("content") or "").strip()
        if not content:
            continue
        if role in {"user", "human"}:
            messages.append(HumanMessage(content=content))
        elif role in {"ai", "assistant", "tutor"}:
            messages.append(AIMessage(content=content))
    latest_content = wrap_file_context(file_text, message) if file_text else message.strip()
    messages.append(HumanMessage(content=latest_content))

    tools = get_tools()
    tools_by_name = {tool.name: tool for tool in tools}
    model = build_chat_model().bind_tools(tools)
    action = None
    prefill = None

    try:
        for _iteration in range(1, MAX_AGENT_ITERATIONS + 1):
            aggregate = None
            text_chunks: list[str] = []
            async for chunk in model.astream(messages):
                aggregate = chunk if aggregate is None else aggregate + chunk
                if isinstance(chunk.content, str) and chunk.content:
                    text_chunks.append(chunk.content)

            if aggregate is None:
                raise RuntimeError("Tutor model returned an empty stream.")
            calls = aggregate.tool_calls or []
            if not calls:
                for token in text_chunks:
                    yield {"type": "token", "content": token}
                yield {
                    "type": "done",
                    "side_data": {
                        **({"action": action} if action else {}),
                        **({"prefill": prefill} if prefill else {}),
                    },
                }
                return

            messages.append(aggregate)
            for call in calls:
                name = call.get("name", "")
                yield {"type": "tool_start", "tool": name}
                tool = tools_by_name.get(name)
                if tool is None:
                    output, error = '{"error":"Unknown tool."}', "Unknown tool."
                else:
                    tool_args = call.get("args") or {}
                    if name == "search_document":
                        tool_args["session_id"] = session_id
                    output, error, duration_ms = await execute_tool(tool, tool_args)
                    logger.info("Tutor stream tool %s completed in %.1fms (error=%s)", name, duration_ms, bool(error))

                if name == "request_quiz_form" and not error:
                    try:
                        import json
                        topic = json.loads(output).get("topic", "")
                        action = "show_quiz_form"
                        if topic:
                            prefill = {"topic": topic}
                    except (TypeError, ValueError):
                        pass

                messages.append(ToolMessage(content=output, tool_call_id=call.get("id", name)))
                yield {"type": "tool_done", "tool": name}

        async for chunk in build_chat_model().astream(
            messages + [HumanMessage(content="Answer the student using the tool results above. Do not call more tools.")]
        ):
            if isinstance(chunk.content, str) and chunk.content:
                yield {"type": "token", "content": chunk.content}
        yield {
            "type": "done",
            "side_data": {
                **({"action": action} if action else {}),
                **({"prefill": prefill} if prefill else {}),
            },
        }
    except Exception:
        logger.exception("Tutor streaming agent failed")
        yield {"type": "error", "message": "Tutor service error. Please try again."}
