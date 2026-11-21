"""DRF endpoints for the Django-native tutor agent."""

import asyncio
import json
import logging
import uuid

from asgiref.sync import async_to_sync, sync_to_async
from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tutor.models import TutorMessage
from apps.tutor.serializers import (
    TutorChatRequestSerializer,
    TutorDocumentUploadSerializer,
    TutorQuizFromAgentSerializer,
    TutorSessionRenameSerializer,
)
from apps.tutor.agent.runner import TutorAgent
from apps.tutor.conversations import TutorConversationStore, preview_message

logger = logging.getLogger(__name__)


def _error_response(exc: Exception) -> Response:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        logger.warning("Tutor request timed out: %s", exc)
        return Response({"error": "Tutor request timed out. Please try again."}, status=504)
    logger.exception("Tutor request failed")
    return Response({"error": "Tutor service is temporarily unavailable."}, status=503)


def _maybe_index_upload(file_bytes: bytes, filename: str, session_id: str) -> None:
    """Best-effort pgvector indexing so follow-up turns can retrieve the upload."""
    if not getattr(settings, "OPENAI_API_KEY", None):
        return
    try:
        from hashlib import sha256

        from apps.tutor.rag_indexing import index_document_bytes
        from apps.tutor.retrieval import rag_engine

        source_key = f"upload:{session_id}:{sha256(file_bytes).hexdigest()}"
        index_document_bytes(
            source_key=source_key,
            source_name=filename,
            filename=filename,
            file_bytes=file_bytes,
            embeddings=rag_engine.embeddings,
            source_metadata={
                "source_type": "session_upload",
                "session_id": session_id,
                "file_name": filename,
            },
        )
    except Exception:
        logger.exception("Tutor upload indexing failed for %s", filename)


class TutorChatView(APIView):
    """POST /api/tutor/chat/ — return one tutor response and agent metadata."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TutorChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        try:
            session = TutorConversationStore.get_or_create_session(request.user, payload)
            if session is not None:
                payload["session_id"] = session.session_id
                payload["history"] = TutorConversationStore.history_for_session(
                    session, payload["history"]
                )
        except Exception as exc:
            return _error_response(exc)
        if session is None:
            return Response({"error": "Tutor session was not found."}, status=404)
        try:
            result = async_to_sync(TutorAgent(**payload).run)()
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
        except Exception as exc:
            return _error_response(exc)

        try:
            TutorConversationStore.save_turn(session, payload["message"], result.response)
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
            session = TutorConversationStore.get_or_create_session(request.user, payload)
            if session is not None:
                payload["session_id"] = session.session_id
                payload["history"] = TutorConversationStore.history_for_session(
                    session, payload["history"]
                )
        except Exception as exc:
            return _error_response(exc)
        if session is None:
            return Response({"error": "Tutor session was not found."}, status=404)

        async def event_stream():
            response_parts = []
            saved = False
            # Tell the client the real (backend-assigned) session_id immediately.
            yield f"data: {json.dumps({'type': 'session', 'session_id': session.session_id})}\n\n"
            try:
                agent = TutorAgent(**payload)
                async for event in agent.stream():
                    if event.get("type") == "token":
                        response_parts.append(event.get("content", ""))
                    elif event.get("type") == "done" and not saved:
                        await sync_to_async(
                            TutorConversationStore.save_turn,
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

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TutorDocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        upload = data["file_upload"]
        filename = upload.name
        message = (data.get("message") or "").strip() or "Analyze the uploaded document."

        from apps.tutor.rag_indexing import extract_documents

        file_bytes = upload.read()
        try:
            documents = extract_documents(file_bytes, filename)
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
            session = TutorConversationStore.get_or_create_session(request.user, payload)
            if session is None:
                return Response({"error": "Tutor session was not found."}, status=404)
            payload["session_id"] = session.session_id
            payload["history"] = TutorConversationStore.history_for_session(
                session, payload["history"]
            )
        except Exception as exc:
            return _error_response(exc)

        try:
            result = async_to_sync(TutorAgent(**payload).run)()
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
        except Exception as exc:
            return _error_response(exc)

        try:
            TutorConversationStore.save_turn(session, message, result.response)
        except Exception as exc:
            return _error_response(exc)

        _maybe_index_upload(file_bytes, filename, session.session_id)

        return Response({
            "response": result.response,
            "session_id": session.session_id,
            "filename": filename,
        })


class TutorQuizFromAgentView(APIView):
    """POST /api/tutor/quiz/from-agent/ — generate a quiz for the inline quiz card."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TutorQuizFromAgentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        topic = data["topic"].strip()

        from apps.tutor.agent.tools.content import generate_quiz

        try:
            quiz_data = dict(async_to_sync(generate_quiz)(
                subject=topic,
                num_mcq=int(data.get("num_questions", 10)),
                num_short=0,
                difficulty="medium",
            ))
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
        except Exception:
            logger.exception("Tutor quiz generation failed for topic=%r", topic)
            return Response({"error": "Quiz generation failed."}, status=503)

        quiz_data["id"] = uuid.uuid4().hex
        quiz_data["time_limit"] = int(data.get("time_limit", 15))
        quiz_data["created_at"] = None
        quiz_data["source_filename"] = ""

        session_id = data.get("session_id")
        if session_id:
            session = TutorConversationStore.get_session(request.user, session_id)
            if session is not None:
                # Persist as a __QUIZ__: message so the card survives session reloads.
                TutorMessage.objects.create(
                    session=session,
                    sender="ai",
                    content=f"__QUIZ__:{json.dumps(quiz_data)}",
                )

        return Response({"quiz_data": quiz_data})


class TutorSessionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            sessions = TutorConversationStore.list_sessions(request.user)
            return Response({"history": [
                {
                    "id": session.pk,
                    "session_id": session.session_id,
                    "title": session.title,
                    "message_count": session.message_count,
                    "last_message": preview_message(session.last_message or ""),
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
            session = TutorConversationStore.get_session(request.user, session_id)
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
            session = TutorConversationStore.rename_session(
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
            deleted_count, deleted_session_id = TutorConversationStore.delete_session(
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