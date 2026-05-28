"""
High-Performance Async Proxy View for Quiz Generation

Implements the Asynchronous Proxy Pattern for quiz endpoints.
"""

import asyncio
import json
import logging
import httpx
from datetime import datetime
from time import perf_counter
from asgiref.sync import sync_to_async
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from apps.core.async_client import call_fastapi, build_fastapi_headers
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import QuizSession, TopicPerformance, QuizTopicSchedule

logger = logging.getLogger(__name__)


async def _record_ai_latency(feature: str, duration_ms: int) -> None:
    try:
        from apps.dashboard.models import AIResponseLatency
        await sync_to_async(AIResponseLatency.objects.create)(
            feature=feature, duration_ms=duration_ms
        )
    except Exception:
        pass


async def _get_authenticated_user_async(request):
    """
    Async-safe token authentication for async views.
    """
    try:
        auth_result = await sync_to_async(
            TokenAuthentication().authenticate,
            thread_sensitive=True
        )(request)
    except AuthenticationFailed as exc:
        return None, JsonResponse({"detail": str(exc)}, status=401)

    if auth_result is None:
        return None, JsonResponse(
            {"detail": "Authentication credentials were not provided."},
            status=401
        )

    user, _token = auth_result
    if not user or not user.is_active:
        return None, JsonResponse({"detail": "Invalid user."}, status=401)

    return user, None


@csrf_exempt
@require_http_methods(["POST"])
async def extract_youtube_transcript(request):
    """
    Extract transcript text from a YouTube URL.
    Returns the same shape as ajax-extract-text so the frontend feeds it
    straight into the existing quiz generation flow.
    """
    try:
        data = json.loads(request.body) if request.body else {}
        url = (data.get("url") or "").strip()
        if not url:
            logger.info("YouTube extract request rejected reason=missing_url")
            return JsonResponse({"error": "YouTube URL is required"}, status=400)

        from .youtube_api import fetch_youtube_quiz_content
        logger.info("YouTube extract request started")
        result = await fetch_youtube_quiz_content(url)

        logger.info(
            "YouTube extract request succeeded video_id=%s title=%r chars=%d",
            result["video_id"],
            result["title"],
            len(result["text"]),
        )
        return JsonResponse({
            "text": result["text"],
            "title": result["title"],
            "video_id": result["video_id"],
        })

    except ValueError as exc:
        logger.warning("YouTube extract request failed reason=%s", exc)
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        logger.error("YouTube extract request failed unexpectedly reason=%s", exc, exc_info=True)
        return JsonResponse({"error": "Failed to fetch transcript from YouTube"}, status=500)



@csrf_exempt
@require_http_methods(["POST"])
async def generate_quiz_api_async(request):
    """
    High-performance async proxy for quiz generation endpoint.
    
    React-facing endpoint to generate a quiz via FastAPI.
    """
    try:
        # Parse request
        data = json.loads(request.body) if request.body else {}
        
        subject = (data.get("subject") or "General").strip()
        study_text = data.get('extractedText', '').strip()
        num_mcq = data.get("num_mcq") or 7
        num_short = data.get("num_short") or 0
        difficulty = (data.get("difficulty") or "medium").strip().lower()
        source_type = (data.get("source_type") or "text").strip().lower()
        source_title = (data.get("source_filename") or "").strip()
        
        if not subject:
            return JsonResponse({"error": "Subject is required"}, status=400)
        
        try:
            num_mcq = int(num_mcq)
        except (TypeError, ValueError):
            num_mcq = 7
        
        num_mcq = max(1, min(num_mcq, 30))
        num_short = max(0, min(int(num_short or 0), 10))
        
        # Validate study text
        if not study_text or len(study_text.strip()) < 30:
            return JsonResponse({"error": "Study text must be at least 30 characters"}, status=400)
        
        if len(study_text) > 50000:
            study_text = study_text[:50000]
            logger.warning("Study text truncated to 50,000 characters")
        
        payload = {
            "subject": subject,
            "study_text": study_text.strip(),
            "num_mcq": int(num_mcq),
            "num_short": int(num_short),
            "difficulty": difficulty,
            "source_type": source_type,
            "source_title": source_title,
        }
        
        # Forward to FastAPI using async client
        headers = build_fastapi_headers()
        
        _t0 = perf_counter()
        fastapi_resp = await call_fastapi(
            "POST",
            "/quiz/",
            json=payload,
            headers=headers,
            timeout=120.0,
        )
        asyncio.create_task(_record_ai_latency('quiz', int((perf_counter() - _t0) * 1000)))

        if fastapi_resp.status_code != 200:
            logger.warning(f"FastAPI quiz call failed: {fastapi_resp.status_code} {fastapi_resp.text}")
            return JsonResponse(
                {"error": "Quiz service temporarily unavailable"}, 
                status=503
            )
        
        quiz_data = fastapi_resp.json()
        
        # Add metadata for frontend compatibility
        import uuid
        quiz_data['id'] = str(uuid.uuid4())
        # Convert time_limit to integer (minutes) to prevent NaN in frontend timer
        quiz_data['time_limit'] = int(data.get('quiz_time', 10))
        quiz_data['created_at'] = None  # Can be set if storing in DB
        quiz_data['source_filename'] = data.get('source_filename', '')
        
        return JsonResponse(quiz_data)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except httpx.TimeoutException:
        logger.error("FastAPI quiz request timed out")
        return JsonResponse({"error": "Request timeout"}, status=504)
    except httpx.RequestError as e:
        logger.error(f"FastAPI quiz request error: {e}")
        return JsonResponse({"error": "Service unavailable"}, status=503)
    except Exception as e:
        logger.error(f"Error calling FastAPI quiz endpoint: {e}", exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
async def submit_quiz_api_async(request):
    """
    High-performance async endpoint to submit quiz answers and calculate scores.
    
    For MCQ: Compares answer letters directly
    For Short Answer: Uses LLM to evaluate if answer is correct
    
    Receives user answers and quiz data, calculates score, and returns results.
    """
    try:
        user, auth_error = await _get_authenticated_user_async(request)
        if auth_error:
            return auth_error

        # Parse request
        data = json.loads(request.body) if request.body else {}
        
        quiz_data = data.get("quiz_data")  # Full quiz data with questions
        user_answers = data.get("user_answers", {})  # {question_index: answer}
        quiz_id = data.get("quiz_id")
        
        if not quiz_data:
            return JsonResponse({"error": "Quiz data is required"}, status=400)
        
        # Extract questions from quiz data
        mcq_questions = quiz_data.get("mcq_questions", [])
        short_questions = quiz_data.get("short_questions", [])
        all_questions = mcq_questions + short_questions
        
        if not all_questions:
            return JsonResponse({"error": "No questions found in quiz data"}, status=400)
        
        # Calculate scores
        total_questions = len(all_questions)
        correct_count = 0
        details = []
        
        for idx, question in enumerate(all_questions):
            user_answer = user_answers.get(str(idx), "").strip()
            correct_answer = question.get("answer", "").strip()
            options = question.get("options", []) or []
            is_correct = False
            reasoning = ""

            def _format_mcq_answer(answer_value: str) -> str:
                if not answer_value:
                    return ""

                normalized = answer_value.strip()
                if not options:
                    return normalized

                letter = normalized.upper()[0]
                option_index = ord(letter) - ord("A")
                if 0 <= option_index < len(options):
                    option_text = str(options[option_index]).strip()
                    return f"{letter}. {option_text}"

                for option_index, option_text in enumerate(options):
                    option_text = str(option_text).strip()
                    if normalized.lower() == option_text.lower():
                        return f"{chr(ord('A') + option_index)}. {option_text}"

                return normalized

            user_answer_display = _format_mcq_answer(user_answer) if (question.get("type") == "mcq" or options) else user_answer
            correct_answer_display = _format_mcq_answer(correct_answer) if (question.get("type") == "mcq" or options) else correct_answer
            
            # For MCQ, compare answer letter (A, B, C, D)
            if question.get("type") == "mcq" or question.get("options"):
                # Normalize answers - handle both "A" and "Option A" formats
                user_letter = user_answer.upper()[0] if user_answer else ""
                correct_letter = correct_answer.upper()[0] if correct_answer else ""
                is_correct = user_letter == correct_letter
                reasoning = "MCQ evaluation: Answer letter matched" if is_correct else "MCQ evaluation: Answer letter did not match"
            else:
                # For short answer, use LLM to evaluate
                question_text = question.get("question", "")
                evaluation = await _evaluate_short_answer(question_text, correct_answer, user_answer)
                is_correct = evaluation.get("is_correct", False)
                reasoning = evaluation.get("reasoning", "Evaluation complete")
            
            if is_correct:
                correct_count += 1
            
            details.append({
                "question_index": idx,
                "question": question.get("question", ""),
                "options": options,
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "user_answer_display": user_answer_display,
                "correct_answer_display": correct_answer_display,
                "is_correct": is_correct,
                "explanation": question.get("explanation", ""),
                "reasoning": reasoning
            })
        
        score_percent = round((correct_count / total_questions) * 100, 1) if total_questions > 0 else 0
        
        results = {
            "quiz_id": quiz_id,
            "subject": quiz_data.get("subject", "Unknown"),
            "difficulty": quiz_data.get("difficulty", "medium"),
            "source_filename": quiz_data.get("source_filename", ""),  # Include source filename
            "score": correct_count,
            "total": total_questions,
            "score_percent": score_percent,
            "details": details,
            "submitted_at": datetime.now()
        }

        subject_clean = (quiz_data.get("subject", "General") or "General")[:100]
        exam_mode = bool(data.get("exam_mode", False))

        # Persist to quiz history for this authenticated user (including admins).
        await sync_to_async(QuizSession.objects.create, thread_sensitive=True)(
            user=user,
            subject=subject_clean,
            total_questions=total_questions,
            correct_answers=correct_count,
            score_percentage=score_percent,
            duration_minutes=int(data.get("duration_minutes") or 0),
            questions_data=quiz_data,
            user_answers=user_answers,
            exam_mode=exam_mode,
            time_limit_minutes=int(data.get("time_limit") or 0) or None,
        )

        # Update Tier 1 intelligence models (fire-and-forget; errors are logged, never bubble up)
        try:
            await _update_topic_performance(user, subject_clean, correct_count, total_questions)
        except Exception as exc:
            logger.warning("TopicPerformance update failed: %s", exc)
        try:
            await _update_quiz_schedule(user, subject_clean, score_percent)
        except Exception as exc:
            logger.warning("QuizTopicSchedule update failed: %s", exc)

        logger.info(f"Quiz submitted: {correct_count}/{total_questions} correct ({score_percent}%)")
        
        return JsonResponse(results)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"Error processing quiz submission: {e}", exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)


async def _evaluate_short_answer(question_text: str, correct_answer: str, user_answer: str) -> dict:
    """
    Evaluate a short answer via the agent evaluate_answer tool.

    Returns:
        {"is_correct": bool, "reasoning": str, "score": float}
    """
    if not user_answer.strip():
        return {"is_correct": False, "reasoning": "No answer provided", "score": 0.0}

    try:
        headers = build_fastapi_headers()
        response = await call_fastapi(
            "POST",
            "/agent/call",
            json={
                "tool_use_id": "quiz_eval",
                "name": "evaluate_answer",
                "input": {
                    "question": question_text,
                    "correct_answer": correct_answer,
                    "user_answer": user_answer,
                },
            },
            headers=headers,
            timeout=30.0,
        )

        if response.status_code != 200:
            logger.warning("Agent evaluate_answer returned %s", response.status_code)
            raise ValueError(f"Agent call failed: {response.status_code}")

        data = response.json()
        output = data.get("output", {})
        return {
            "is_correct": bool(output.get("is_correct", False)),
            "reasoning": str(output.get("reasoning", "Evaluation complete")),
            "score": float(output.get("score", 0.0)),
        }

    except Exception as exc:
        logger.warning("Short-answer evaluation via agent failed: %s — falling back to string match", exc)
        is_correct = user_answer.strip().lower() == correct_answer.strip().lower()
        return {
            "is_correct": is_correct,
            "reasoning": "String match fallback.",
            "score": 1.0 if is_correct else 0.0,
        }

def _score_to_sm2_quality(score_percent: float) -> int:
    """Map quiz score percentage to SM-2 quality rating (0–5)."""
    if score_percent >= 90:
        return 5
    if score_percent >= 75:
        return 4
    if score_percent >= 60:
        return 3
    if score_percent >= 40:
        return 2
    if score_percent >= 20:
        return 1
    return 0


def _update_topic_performance_sync(user, topic: str, correct: int, total: int):
    """Sync helper: update or create TopicPerformance row for user/topic."""
    from django.db.models import F
    tp, created = TopicPerformance.objects.get_or_create(
        user=user,
        topic=topic,
        defaults={
            'subject': topic,
            'total_questions': total,
            'correct_answers': correct,
            'accuracy': round(correct / total * 100, 2) if total > 0 else 0.0,
        },
    )
    if not created:
        tp.total_questions = F('total_questions') + total
        tp.correct_answers = F('correct_answers') + correct
        tp.save(update_fields=['total_questions', 'correct_answers'])
        tp.refresh_from_db(fields=['total_questions', 'correct_answers'])
        tp.accuracy = round(tp.correct_answers / tp.total_questions * 100, 2) if tp.total_questions > 0 else 0.0
        tp.save(update_fields=['accuracy'])


def _update_quiz_schedule_sync(user, topic: str, score_percent: float):
    """Sync helper: run SM-2 update on QuizTopicSchedule for user/topic."""
    from apps.flashcards.scheduling import update_sm2
    schedule, _ = QuizTopicSchedule.objects.get_or_create(
        user=user,
        topic=topic,
        defaults={'subject': topic},
    )
    update_sm2(schedule, _score_to_sm2_quality(score_percent))


async def _update_topic_performance(user, topic: str, correct: int, total: int):
    await sync_to_async(_update_topic_performance_sync, thread_sensitive=True)(user, topic, correct, total)


async def _update_quiz_schedule(user, topic: str, score_percent: float):
    await sync_to_async(_update_quiz_schedule_sync, thread_sensitive=True)(user, topic, score_percent)


class QuizHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = QuizSession.objects.filter(
            user=request.user
        ).order_by('-created_at')[:20]

        data = [{
            'id':             s.id,
            'subject':        s.subject,
            'total_questions': s.total_questions,
            'correct_answers': s.correct_answers,
            'score_percent':  float(s.score_percentage),
            'created_at':     s.created_at.isoformat(),
            'exam_mode':      s.exam_mode,
        } for s in sessions]

        return Response({'history': data})


class QuizReplayView(APIView):
    """GET /api/quiz/sessions/<session_id>/ — return the stored quiz data for replaying."""
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        try:
            session = QuizSession.objects.get(id=session_id, user=request.user)
        except QuizSession.DoesNotExist:
            return Response({'error': 'Quiz session not found.'}, status=404)

        return Response({'quiz_data': session.questions_data})


class WeakAreasView(APIView):
    """GET /api/quiz/weak-areas/ — bottom 5 topics by accuracy (min 3 questions)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        weak = TopicPerformance.objects.filter(
            user=request.user,
            total_questions__gte=3,
        ).order_by('accuracy')[:5]

        data = [{
            'topic':           tp.topic,
            'subject':         tp.subject,
            'total_questions': tp.total_questions,
            'correct_answers': tp.correct_answers,
            'accuracy':        round(tp.accuracy, 1),
            'last_attempted':  tp.last_attempted.isoformat(),
        } for tp in weak]

        return Response({'weak_areas': data})


class DueTopicsView(APIView):
    """GET /api/quiz/due-topics/ — topics where next_review <= now, ordered most overdue first."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.utils import timezone
        due = QuizTopicSchedule.objects.filter(
            user=request.user,
            next_review__lte=timezone.now(),
        ).order_by('next_review')

        data = [{
            'topic':       s.topic,
            'subject':     s.subject,
            'next_review': s.next_review.isoformat(),
            'last_review': s.last_review.isoformat() if s.last_review else None,
            'interval':    s.interval,
        } for s in due]

        return Response({'due_topics': data})
