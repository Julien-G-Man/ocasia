"""Stateful tool-calling tutor agent built on LangChain messages and tools."""

import logging
from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from apps.tutor.agent.executor import execute_tool
from apps.tutor.agent.llm import build_chat_model
from apps.tutor.agent.prompts import build_tutor_system_prompt, wrap_file_context
from apps.tutor.agent.registry import get_tools
from apps.tutor.agent.schemas import TutorAgentResult

logger = logging.getLogger(__name__)

MAX_AGENT_ITERATIONS = 10

_USER_ROLES = {"user", "human"}
_AI_ROLES = {"ai", "assistant", "tutor"}


def _message_content(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "") for item in content if isinstance(item, dict)
        ).strip()
    return str(content or "").strip()


class TutorAgent:
    """One tutor turn: configuration, conversation state, and the tool loop.

    The view constructs an instance per request and calls :meth:`run` for a
    buffered answer or :meth:`stream` for token/tool events. Persistence and
    HTTP concerns stay outside the agent.
    """

    def __init__(
        self,
        message: str,
        history=(),
        *,
        tutor_mode: str = "direct",
        user_stats: dict | None = None,
        file_text: str | None = None,
        session_id: str | None = None,
        has_document: bool = False,
        max_iterations: int = MAX_AGENT_ITERATIONS,
    ) -> None:
        self.message = message
        self.history = history
        self.tutor_mode = tutor_mode
        self.user_stats = user_stats
        self.file_text = file_text
        self.session_id = session_id
        self.has_document = has_document
        self.max_iterations = max_iterations

        self.messages = self._build_messages()
        self.tool_calls_made: list[str] = []
        self.action: str | None = None
        self.prefill: dict | None = None

        self._tools = None
        self._tools_by_name: dict = {}
        self._base_model = None
        self._model = None

    def _build_messages(self) -> list:
        messages = [
            SystemMessage(
                content=build_tutor_system_prompt(
                    tutor_mode=self.tutor_mode, user_stats=self.user_stats
                )
            )
        ]
        for item in self.history:
            role = item.get("message_type") or item.get("role")
            content = (item.get("content") or "").strip()
            if not content:
                continue
            if role in _USER_ROLES:
                messages.append(HumanMessage(content=content))
            elif role in _AI_ROLES:
                messages.append(AIMessage(content=content))
        latest = (
            wrap_file_context(self.file_text, self.message)
            if self.file_text
            else self.message.strip()
        )
        messages.append(HumanMessage(content=latest))
        return messages

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        self._tools = get_tools()
        self._tools_by_name = {tool.name: tool for tool in self._tools}
        self._base_model = build_chat_model()
        self._model = self._base_model.bind_tools(self._tools)

    async def _run_tool(self, call: dict) -> tuple[str, str]:
        name = call.get("name", "")
        self.tool_calls_made.append(name)
        tool = self._tools_by_name.get(name)
        if tool is None:
            output, error = '{"error":"Unknown tool."}', "Unknown tool."
        else:
            tool_args = call.get("args") or {}
            if name == "search_document":
                tool_args["session_id"] = self.session_id
            output, error, duration_ms = await execute_tool(tool, tool_args)
            logger.info(
                "Tutor tool %s completed in %.1fms (error=%s)",
                name,
                duration_ms,
                bool(error),
            )

        if name == "request_quiz_form" and not error:
            self._record_quiz_form(output)
        return output, call.get("id", name)

    def _record_quiz_form(self, output: str) -> None:
        import json

        try:
            topic = json.loads(output).get("topic", "")
            self.action = "show_quiz_form"
            if topic:
                self.prefill = {"topic": topic}
        except (TypeError, ValueError):
            pass

    def _side_data(self) -> dict:
        side_data: dict = {}
        if self.action:
            side_data["action"] = self.action
        if self.prefill:
            side_data["prefill"] = self.prefill
        return side_data

    def _result(self, response: str) -> TutorAgentResult:
        return TutorAgentResult(
            response=response,
            tool_calls_made=self.tool_calls_made,
            action=self.action,
            prefill=self.prefill,
        )

    async def run(self) -> TutorAgentResult:
        if not self.message or not self.message.strip():
            raise ValueError("message must not be empty")
        self._ensure_model()

        for _iteration in range(1, self.max_iterations + 1):
            ai_message = await self._model.ainvoke(self.messages)
            if not isinstance(ai_message, AIMessage):
                raise RuntimeError("Tutor model returned an unexpected message type.")
            calls = ai_message.tool_calls or []
            if not calls:
                response = _message_content(ai_message.content)
                if not response:
                    raise RuntimeError("Tutor model returned an empty response.")
                return self._result(response)

            self.messages.append(ai_message)
            for call in calls:
                output, tool_call_id = await self._run_tool(call)
                self.messages.append(
                    ToolMessage(content=output, tool_call_id=tool_call_id)
                )

        logger.warning("Tutor agent reached the %d-iteration limit", self.max_iterations)
        final = await self._base_model.ainvoke(
            self.messages
            + [
                HumanMessage(
                    content=(
                        "Give the student the best concise answer using the tool "
                        "results above. Do not call more tools."
                    )
                )
            ]
        )
        response = _message_content(final.content)
        if not response:
            raise RuntimeError("Tutor agent stopped before producing a final response.")
        return self._result(response)

    async def stream(self) -> AsyncIterator[dict]:
        if not self.message or not self.message.strip():
            yield {"type": "error", "message": "message must not be empty"}
            return
        self._ensure_model()

        try:
            for _iteration in range(1, self.max_iterations + 1):
                aggregate = None
                text_chunks: list[str] = []
                async for chunk in self._model.astream(self.messages):
                    aggregate = chunk if aggregate is None else aggregate + chunk
                    if isinstance(chunk.content, str) and chunk.content:
                        text_chunks.append(chunk.content)

                if aggregate is None:
                    raise RuntimeError("Tutor model returned an empty stream.")
                calls = aggregate.tool_calls or []
                if not calls:
                    for token in text_chunks:
                        yield {"type": "token", "content": token}
                    yield {"type": "done", "side_data": self._side_data()}
                    return

                self.messages.append(aggregate)
                for call in calls:
                    name = call.get("name", "")
                    yield {"type": "tool_start", "tool": name}
                    output, tool_call_id = await self._run_tool(call)
                    self.messages.append(
                        ToolMessage(content=output, tool_call_id=tool_call_id)
                    )
                    yield {"type": "tool_done", "tool": name}

            async for chunk in self._base_model.astream(
                self.messages
                + [
                    HumanMessage(
                        content=(
                            "Answer the student using the tool results above. "
                            "Do not call more tools."
                        )
                    )
                ]
            ):
                if isinstance(chunk.content, str) and chunk.content:
                    yield {"type": "token", "content": chunk.content}
            yield {"type": "done", "side_data": self._side_data()}
        except Exception:
            logger.exception("Tutor streaming agent failed")
            yield {"type": "error", "message": "Tutor service error. Please try again."}