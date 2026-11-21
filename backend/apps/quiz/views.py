"""Quiz API views — HTTP handling only; business logic lives in ``services``."""

import logging
import uuid

from asgiref.sync import async_to_sync
from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.ai_engine import APIIntegrationError
from apps.quiz.services import  (generate_quiz, submit_quiz, 
    list_history, get_replay, list_weak_areas, list_due_topics)
from apps.quiz.models import QuizSession
from apps.quiz.serializers import (
    QuizGenerateRequestSerializer,
    QuizSubmitRequestSerializer,
    QuizYouTubeRequestSerializer,
)
from apps.quiz.utils.download_helpers import build_download
from apps.quiz.utils.extract_text import extract_file_text
from apps.quiz.utils.youtube_api import fetch_youtube_quiz_content

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_STUDY_TEXT = 50_000


class QuizGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = QuizGenerateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        study_text = (data.get("extractedText") or "").strip()
        if len(study_text) < 30:
            return Response(
                {"error": "Study text must be at least 30 characters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            quiz = async_to_sync(generate_quiz)(
                subject=(data.get("subject") or "General").strip(),
                study_text=study_text[:MAX_STUDY_TEXT],
                difficulty=(data.get("difficulty") or "medium").strip().lower(),
                num_mcq=data.get("num_mcq", 7),
                num_short=data.get("num_short", 0),
                source_type=(data.get("source_type") or "text").strip().lower(),
                source_title=(data.get("source_filename") or "").strip(),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except APIIntegrationError as exc:
            logger.warning("Quiz generation failed: %s", exc)
            return Response(
                {"error": "Quiz service temporarily unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        quiz["id"] = str(uuid.uuid4())
        quiz["time_limit"] = int(data.get("quiz_time", 10))
        quiz["created_at"] = None
        quiz["source_filename"] = (data.get("source_filename") or "").strip()
        return Response(quiz)


class QuizSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = QuizSubmitRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            results = async_to_sync(submit_quiz)(
                user=request.user,
                quiz_data=data["quiz_data"],
                user_answers=data.get("user_answers") or {},
                quiz_id=data.get("quiz_id"),
                duration_minutes=data.get("duration_minutes", 0),
                time_limit=data.get("time_limit", 0),
                exam_mode=data.get("exam_mode", False),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(results)


class QuizExtractTextView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file = request.FILES.get("slide_file")
        if not file:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
        if file.size > MAX_UPLOAD_BYTES:
            return Response({"error": "File too large (max 10MB)"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            text = extract_file_text(file)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Text extraction failed")
            return Response(
                {"error": "Failed to extract text from file. Please try a different file."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not text:
            return Response(
                {
                    "error": (
                        "No text could be extracted from this file. "
                        "If this is a scanned/image-based PDF (common with matrix-heavy slides), "
                        "please export to DOCX/TXT or upload a text-based PDF."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(text) > MAX_STUDY_TEXT:
            text = text[: MAX_STUDY_TEXT - 100] + "... [truncated]"

        return Response({"text": text})


class QuizYouTubeExtractView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = QuizYouTubeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = async_to_sync(fetch_youtube_quiz_content)(serializer.validated_data["url"])
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result)


class QuizDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        results = request.data.get("results", {})
        file_format = (request.data.get("format") or "pdf").lower()
        if not results:
            return Response({"error": "No results data provided"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            content, content_type, filename = build_download(results, file_format)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class QuizHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(list_history(request.user))


class QuizReplayView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        try:
            return Response(get_replay(request.user, session_id))
        except QuizSession.DoesNotExist:
            return Response({"error": "Quiz session not found."}, status=status.HTTP_404_NOT_FOUND)


class WeakAreasView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(list_weak_areas(request.user))


class DueTopicsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(list_due_topics(request.user))
