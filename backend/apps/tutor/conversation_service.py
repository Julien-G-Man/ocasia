"""Persistence and ownership rules for tutor conversations."""

import uuid

from django.db import transaction

from apps.tutor.models import TutorMessage, TutorSession


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
