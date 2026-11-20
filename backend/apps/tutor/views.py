"""DRF endpoints for the Django-native tutor agent."""

import asyncio
import json
import logging
import uuid

from asgiref.sync import async_to_sync, sync_to_async
from django.http import StreamingHttpResponse
from django.db import transaction
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tutor.chat_service import TutorChatService
from apps.tutor.models import TutorMessage, TutorSession
from apps.tutor.serializers import TutorChatRequestSerializer

logger = logging.getLogger(__name__)


def _error_response(exc: Exception) -> Response:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        logger.warning("Tutor request timed out: %s", exc)
        return Response({"error": "Tutor request timed out. Please try again."}, status=504)
    logger.exception("Tutor request failed")
    return Response({"error": "Tutor service is temporarily unavailable."}, status=503)


def _get_or_create_session(request, payload: dict) -> TutorSession | None:
    session_id = payload.get("session_id") or uuid.uuid4().hex
    user = request.user if getattr(request.user, "is_authenticated", False) else None
    session, _created = TutorSession.objects.get_or_create(
        session_id=session_id,
        defaults={"user": user, "has_document": bool(payload.get("has_document"))},
    )

    # Do not reveal whether another user's session identifier exists.
    if session.user_id != (user.pk if user else None):
        return None

    has_document = bool(payload.get("has_document") or payload.get("file_text"))
    if has_document and not session.has_document:
        session.has_document = True
        session.save(update_fields=["has_document"])
    return session


def _history_for_session(session: TutorSession, supplied_history: list[dict]) -> list[dict]:
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


def _save_turn(session: TutorSession, message: str, response: str) -> None:
    with transaction.atomic():
        TutorMessage.objects.bulk_create([
            TutorMessage(session=session, sender="user", content=message),
            TutorMessage(session=session, sender="ai", content=response),
        ])
        if not session.title:
            title = message.strip()
            session.title = title if len(title) <= 120 else f"{title[:117].rstrip()}..."
            session.save(update_fields=["title"])


class TutorChatView(APIView):
    """POST /api/tutor/chat/ — return one tutor response and agent metadata."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TutorChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        try:
            session = _get_or_create_session(request, payload)
            if session is not None:
                payload["session_id"] = session.session_id
                payload["history"] = _history_for_session(session, payload["history"])
        except Exception as exc:
            return _error_response(exc)
        if session is None:
            return Response({"error": "Tutor session was not found."}, status=404)
        try:
            result = async_to_sync(TutorChatService().respond_turn)(**payload)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
        except Exception as exc:
            return _error_response(exc)

        try:
            _save_turn(session, payload["message"], result.response)
        except Exception as exc:
            return _error_response(exc)

        return Response({
            "response": result.response,
            "tool_calls_made": result.tool_calls_made,
            "action": result.action,
            "prefill": result.prefill,
            "session_id": session.session_id,
        })


class TutorChatStreamView(APIView):
    """POST /api/tutor/chat/stream/ — stream tutor lifecycle/token events as SSE."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TutorChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        try:
            session = _get_or_create_session(request, payload)
            if session is not None:
                payload["session_id"] = session.session_id
                payload["history"] = _history_for_session(session, payload["history"])
        except Exception as exc:
            return _error_response(exc)
        if session is None:
            return Response({"error": "Tutor session was not found."}, status=404)

        async def event_stream():
            response_parts = []
            saved = False
            try:
                async for event in TutorChatService().stream_turn(**payload):
                    if event.get("type") == "token":
                        response_parts.append(event.get("content", ""))
                    elif event.get("type") == "done" and not saved:
                        await sync_to_async(_save_turn, thread_sensitive=True)(
                            session,
                            payload["message"],
                            "".join(response_parts),
                        )
                        event["session_id"] = session.session_id
                        saved = True
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as exc:
                if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
                    logger.warning("Streaming tutor request timed out: %s", exc)
                    message = "Tutor request timed out. Please try again."
                else:
                    logger.exception("Streaming tutor request failed")
                    message = "Tutor service is temporarily unavailable."
                yield f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"
        response["X-Tutor-Session-ID"] = session.session_id
        return response
