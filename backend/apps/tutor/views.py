"""DRF endpoints for the Django-native tutor agent."""

import asyncio
import json
import logging

from asgiref.sync import async_to_sync, sync_to_async
from django.http import StreamingHttpResponse
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tutor.serializers import (
    TutorChatRequestSerializer,
    TutorDocumentUploadSerializer,
    TutorSessionRenameSerializer,
)
from apps.tutor.services import TutorChatService, TutorConversationService

logger = logging.getLogger(__name__)


def _error_response(exc: Exception) -> Response:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        logger.warning("Tutor request timed out: %s", exc)
        return Response({"error": "Tutor request timed out. Please try again."}, status=504)
    logger.exception("Tutor request failed")
    return Response({"error": "Tutor service is temporarily unavailable."}, status=503)


class TutorChatView(APIView):
    """POST /api/tutor/chat/ — return one tutor response and agent metadata."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TutorChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        try:
            session = TutorConversationService.get_or_create_session(request.user, payload)
            if session is not None:
                payload["session_id"] = session.session_id
                payload["history"] = TutorConversationService.history_for_session(
                    session, payload["history"]
                )
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
            TutorConversationService.save_turn(session, payload["message"], result.response)
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
            session = TutorConversationService.get_or_create_session(request.user, payload)
            if session is not None:
                payload["session_id"] = session.session_id
                payload["history"] = TutorConversationService.history_for_session(
                    session, payload["history"]
                )
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
                        await sync_to_async(
                            TutorConversationService.save_turn,
                            thread_sensitive=True,
                        )(
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


class TutorDocumentUploadView(APIView):
    """POST /api/tutor/upload/ — extract an uploaded file and return a tutor response."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TutorDocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        upload = data["file_upload"]
        filename = upload.name
        message = (data.get("message") or "").strip() or "Analyze the uploaded document."

        from apps.tutor.rag_indexing import extract_documents

        try:
            documents = extract_documents(upload.read(), filename)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
        except Exception:
            logger.exception("Tutor file extraction failed for %s", filename)
            return Response({"error": "Could not read the uploaded file."}, status=400)

        file_text = "\n\n".join(document.page_content for document in documents).strip()
        if not file_text:
            return Response({"error": "No readable text found in the uploaded file."}, status=400)
        if len(file_text) > 50_000:
            file_text = file_text[:50_000] + "\n... [text truncated due to length]"

        payload = {
            "message": message,
            "history": [],
            "tutor_mode": data.get("tutor_mode", "direct"),
            "session_id": data.get("session_id") or None,
            "file_text": file_text,
            "has_document": True,
        }
        try:
            session = TutorConversationService.get_or_create_session(request.user, payload)
            if session is None:
                return Response({"error": "Tutor session was not found."}, status=404)
            payload["session_id"] = session.session_id
            payload["history"] = TutorConversationService.history_for_session(
                session, payload["history"]
            )
        except Exception as exc:
            return _error_response(exc)

        try:
            result = async_to_sync(TutorChatService().respond_turn)(**payload)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
        except Exception as exc:
            return _error_response(exc)

        try:
            TutorConversationService.save_turn(session, message, result.response)
        except Exception as exc:
            return _error_response(exc)

        return Response({
            "response": result.response,
            "session_id": session.session_id,
            "filename": filename,
        })


class TutorSessionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            sessions = TutorConversationService.list_sessions(request.user)
            return Response({"history": [
                {
                    "id": session.pk,
                    "session_id": session.session_id,
                    "title": session.title,
                    "message_count": session.message_count,
                    "last_message": (session.last_message or "")[:120],
                    "created_at": session.created_at.isoformat(),
                }
                for session in sessions
            ]})
        except Exception as exc:
            return _error_response(exc)


class TutorSessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        try:
            session = TutorConversationService.get_session(request.user, session_id)
            if session is None:
                return Response({"detail": "Session not found."}, status=404)
            messages = session.messages.order_by("created_at", "pk")
            serialized = [{
                "id": message.pk,
                "sender": message.sender,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            } for message in messages]
            return Response({
                "session_id": session.session_id,
                "user": str(request.user),
                "user_id": request.user.pk,
                "message_count": len(serialized),
                "messages": serialized,
            })
        except Exception as exc:
            return _error_response(exc)

    def patch(self, request, session_id):
        serializer = TutorSessionRenameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            session = TutorConversationService.rename_session(
                request.user, session_id, serializer.validated_data["title"]
            )
            if session is None:
                return Response({"detail": "Session not found."}, status=404)
            return Response({
                "status": "success",
                "session_id": session.session_id,
                "title": session.title,
            })
        except Exception as exc:
            return _error_response(exc)

    def delete(self, request, session_id):
        try:
            deleted_count, deleted_session_id = TutorConversationService.delete_session(
                request.user, session_id
            )
            if deleted_session_id is None:
                return Response({"detail": "Session not found."}, status=404)
            return Response({
                "status": "success",
                "deleted_count": deleted_count,
                "session_id": deleted_session_id,
            })
        except Exception as exc:
            return _error_response(exc)
