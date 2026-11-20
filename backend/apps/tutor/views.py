"""DRF endpoints for the Django-native tutor agent."""

import asyncio
import json
import logging

from asgiref.sync import async_to_sync
from django.http import StreamingHttpResponse
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tutor.chat_service import TutorChatService
from apps.tutor.serializers import TutorChatRequestSerializer

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
    authentication_classes = []

    def post(self, request):
        serializer = TutorChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        try:
            result = async_to_sync(TutorChatService().respond_turn)(**payload)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
        except Exception as exc:
            return _error_response(exc)

        return Response({
            "response": result.response,
            "tool_calls_made": result.tool_calls_made,
            "action": result.action,
            "prefill": result.prefill,
            "session_id": payload.get("session_id"),
        })


class TutorChatStreamView(APIView):
    """POST /api/tutor/chat/stream/ — stream tutor lifecycle/token events as SSE."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = TutorChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        async def event_stream():
            try:
                async for event in TutorChatService().stream_turn(**payload):
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
        return response
