import uuid
from functools import lru_cache
from django.conf import settings
from collections.abc import Sequence
from collections.abc import AsyncIterator
from django.db.models import Count, OuterRef, Subquery
from django.db import transaction

from apps.tutor.agent.schemas import TutorAgentResult
from apps.tutor.models import TutorMessage, TutorSession


@lru_cache(maxsize=1)
def build_chat_model():
    """LangChain chat model used by tutor and its tools."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError(
            "LangChain OpenAI integration is missing. Install langchain-openai."
        ) from exc

    api_key = getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be configured for the tutor model.")

    return ChatOpenAI(
        api_key=api_key,
        model=getattr(settings, "TUTOR_MODEL", "gpt-4o-mini"),
        temperature=getattr(settings, "TUTOR_TEMPERATURE", 0.3),
        max_tokens=getattr(settings, "CHATBOT_MAX_TOKENS", 1200),
    )


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

        from apps.tutor.agent.runner import run_tutor_agent

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
        from apps.tutor.agent.runner import stream_tutor_agent

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




# Persistence and ownership rules for tutor conversations.

class TutorConversationService:
    """Manage tutor sessions and message history independently of HTTP views."""

    @staticmethod
    def get_or_create_session(user, payload: dict) -> TutorSession | None:
        session_id = payload.get("session_id") or uuid.uuid4().hex
        owner = user if getattr(user, "is_authenticated", False) else None
        session, _created = TutorSession.objects.get_or_create(
            session_id=session_id,
            defaults={"user": owner, "has_document": bool(payload.get("has_document"))},
        )

        # Do not reveal whether another user's session identifier exists.
        if session.user_id != (owner.pk if owner else None):
            return None

        has_document = bool(payload.get("has_document") or payload.get("file_text"))
        if has_document and not session.has_document:
            session.has_document = True
            session.save(update_fields=["has_document"])
        return session

    @staticmethod
    def history_for_session(session: TutorSession, supplied_history: list[dict]) -> list[dict]:
        stored = list(
            session.messages.order_by("-created_at", "-pk").values("sender", "content")[:100]
        )
        if stored:
            stored.reverse()
            return [{"role": row["sender"], "content": row["content"]} for row in stored]

        imported = []
        for item in supplied_history:
            role = (item.get("role") or "").casefold()
            content = (item.get("content") or "").strip()
            if not content:
                continue
            if role in {"user", "human"}:
                sender = "user"
            elif role in {"ai", "assistant", "tutor"}:
                sender = "ai"
            else:
                continue
            imported.append(TutorMessage(session=session, sender=sender, content=content))
        if imported:
            TutorMessage.objects.bulk_create(imported)
        return [{"role": row.sender, "content": row.content} for row in imported]

    @staticmethod
    def save_turn(session: TutorSession, message: str, response: str) -> None:
        with transaction.atomic():
            TutorMessage.objects.bulk_create([
                TutorMessage(session=session, sender="user", content=message),
                TutorMessage(session=session, sender="ai", content=response),
            ])
            if not session.title:
                title = message.strip()
                session.title = title if len(title) <= 120 else f"{title[:117].rstrip()}..."
                session.save(update_fields=["title"])

    @staticmethod
    def list_sessions(user, limit: int = 50):
        latest_message = TutorMessage.objects.filter(
            session_id=OuterRef("pk")
        ).order_by("-created_at", "-pk").values("content")[:1]
        return (
            TutorSession.objects.filter(user=user)
            .annotate(
                message_count=Count("messages"),
                last_message=Subquery(latest_message),
            )
            .order_by("-created_at", "-pk")[:limit]
        )

    @staticmethod
    def get_session(user, session_id: str) -> TutorSession | None:
        return TutorSession.objects.filter(user=user, session_id=session_id).first()

    @staticmethod
    def rename_session(user, session_id: str, title: str) -> TutorSession | None:
        session = TutorConversationService.get_session(user, session_id)
        if session is None:
            return None
        session.title = title[:120]
        session.save(update_fields=["title"])
        return session

    @staticmethod
    def delete_session(user, session_id: str) -> tuple[int, str | None]:
        session = TutorConversationService.get_session(user, session_id)
        if session is None:
            return 0, None
        requested_id = session.session_id
        from apps.tutor.models import TutorDocument

        TutorDocument.objects.filter(metadata__session_id=requested_id).delete()
        deleted_count, _ = session.delete()
        return deleted_count, requested_id
