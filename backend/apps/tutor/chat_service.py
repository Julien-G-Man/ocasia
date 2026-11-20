from collections.abc import Sequence
from collections.abc import AsyncIterator

from apps.tutor.agent.runner import run_tutor_agent, stream_tutor_agent
from apps.tutor.agent.schemas import TutorAgentResult


class TutorChatService:
    """Application boundary for tutor responses.

    Persistence, authentication, and HTTP transport stay outside this class.
    """

    async def respond(
        self,
        message: str,
        history: Sequence[dict[str, str]] = (),
        *,
        tutor_mode: str = "direct",
        user_stats: dict | None = None,
        file_text: str | None = None,
        session_id: str | None = None,
        has_document: bool = False,
    ) -> str:
        result = await self.respond_turn(
            message,
            history,
            tutor_mode=tutor_mode,
            user_stats=user_stats,
            file_text=file_text,
            session_id=session_id,
            has_document=has_document,
        )
        return result.response

    async def respond_turn(
        self,
        message: str,
        history: Sequence[dict[str, str]] = (),
        *,
        tutor_mode: str = "direct",
        user_stats: dict | None = None,
        file_text: str | None = None,
        session_id: str | None = None,
        has_document: bool = False,
    ) -> TutorAgentResult:
        if not message or not message.strip():
            raise ValueError("message must not be empty")

        return await run_tutor_agent(
            message=message,
            history=history,
            tutor_mode=tutor_mode,
            user_stats=user_stats,
            file_text=file_text,
            session_id=session_id,
            has_document=has_document,
        )

    async def stream_turn(
        self,
        message: str,
        history: Sequence[dict[str, str]] = (),
        *,
        tutor_mode: str = "direct",
        user_stats: dict | None = None,
        file_text: str | None = None,
        session_id: str | None = None,
        has_document: bool = False,
    ) -> AsyncIterator[dict]:
        async for event in stream_tutor_agent(
            message=message,
            history=history,
            tutor_mode=tutor_mode,
            user_stats=user_stats,
            file_text=file_text,
            session_id=session_id,
            has_document=has_document,
        ):
            yield event

