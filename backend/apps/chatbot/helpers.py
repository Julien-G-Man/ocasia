import logging
import time
from asgiref.sync import sync_to_async
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import ChatSession, ChatMessage

logger = logging.getLogger(__name__)


def _derive_session_title(user_message: str) -> str:
    text = (user_message or "").strip().replace("\n", " ")
    if not text:
        return "New chat"
    sentence_end = len(text)
    for separator in (". ", "? ", "! ", ".", "?", "!"):
        index = text.find(separator)
        if index != -1:
            sentence_end = min(sentence_end, index + (0 if separator in {".", "?", "!"} else 1))
    title = text[:sentence_end].strip().strip("\"'")
    if len(title) > 120:
        title = title[:117].rstrip() + "..."
    return title or "New chat"


def _prune_old_chat_sessions_sync(user, keep: int = 10, preserve_session_pk=None):
    """Keep only the newest `keep` sessions for a user, deleting older ones."""
    sessions_qs = ChatSession.objects.filter(user=user).order_by("-created_at", "-id")
    keep_ids = list(sessions_qs.values_list("id", flat=True)[:keep])
    if preserve_session_pk is not None:
        keep_ids.append(preserve_session_pk)
    deleted_count, _ = ChatSession.objects.filter(user=user).exclude(id__in=set(keep_ids)).delete()
    return deleted_count


async def _resolve_authenticated_user(request):
    """Resolve authenticated user via DRF token auth for async views."""
    auth_header = request.headers.get("Authorization", "").strip()
    if not auth_header:
        return None
    try:
        auth_result = await sync_to_async(
            TokenAuthentication().authenticate, thread_sensitive=True
        )(request)
    except AuthenticationFailed:
        return None
    except Exception:
        logger.exception("Token authentication failed in chatbot session resolver")
        return None
    if not auth_result:
        return None
    user, _token = auth_result
    return user if user and user.is_active else None


async def _get_or_create_session(request, session_id=None):
    """Get/create chat session for authenticated users."""
    user = await _resolve_authenticated_user(request)
    if not user:
        return None, None

    if session_id is None:
        session_id = f"chat-{user.id}-{int(time.time())}"

    session_obj, created = await sync_to_async(ChatSession.objects.get_or_create)(
        session_id=session_id,
        defaults={"user": user},
    )

    if session_obj.user_id != user.id:
        session_obj.user = user
        await sync_to_async(session_obj.save, thread_sensitive=True)(update_fields=["user"])

    if created:
        logger.debug("Created new session %s for user %s", session_id, user.id)

    deleted_count = await sync_to_async(_prune_old_chat_sessions_sync, thread_sensitive=True)(
        user, keep=10, preserve_session_pk=session_obj.id,
    )
    if deleted_count:
        logger.info("Pruned %s old chat session(s) for user %s", deleted_count, user.id)

    return user, session_obj


async def _save_user_message(session_obj, user_message: str):
    """Save user message to DB for authenticated sessions only."""
    if session_obj is None:
        return None
    try:
        msg_obj = await sync_to_async(ChatMessage.objects.create)(
            session=session_obj, sender="user", content=user_message,
        )
        logger.debug("Saved user message ID %s to session %s", msg_obj.id, session_obj.id)

        if not getattr(session_obj, "title", ""):
            session_obj.title = _derive_session_title(user_message)
            await sync_to_async(session_obj.save, thread_sensitive=True)(update_fields=["title"])

        return msg_obj
    except Exception as exc:
        logger.error("Failed to save user message: %s", exc, exc_info=True)
        raise


async def _save_ai_message(session_obj, ai_message: str):
    """Save AI message to DB for authenticated sessions only."""
    if session_obj is None:
        return None
    try:
        msg_obj = await sync_to_async(ChatMessage.objects.create)(
            session=session_obj, sender="ai", content=ai_message,
        )
        logger.debug("Saved AI message ID %s to session %s", msg_obj.id, session_obj.id)
        return msg_obj
    except Exception as exc:
        logger.error("Failed to save AI message: %s", exc, exc_info=True)
        raise


_QUIZ_MSG_PREFIX = "__QUIZ__:"

def _summarize_message_content(content: str) -> str:
    """Replace quiz data blobs with a short summary for AI context."""
    if content.startswith(_QUIZ_MSG_PREFIX):
        try:
            import json as _json
            data = _json.loads(content[len(_QUIZ_MSG_PREFIX):])
            subject = data.get("subject", "unknown topic")
            n = len(data.get("mcq_questions", []))
            diff = data.get("difficulty", "")
            return f"[Quiz generated: {subject}, {n} questions, {diff} difficulty]"
        except Exception:
            return "[Quiz generated]"
    return content


async def _get_conversation_history(session_obj, limit: int = 10):
    """Get conversation history for context."""
    if session_obj is None:
        return []
    history_qs = await sync_to_async(list)(session_obj.messages.order_by("-created_at")[:limit])
    return [
        {"message_type": msg.sender, "content": _summarize_message_content(msg.content)}
        for msg in reversed(history_qs)
    ]


def chunk_text(text: str, size: int = 500, overlap: int = 100) -> list[str]:
    """
    Split text into overlapping word-based chunks for vector indexing.
    Returns a list of string chunks.
    """
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = start + size
        chunks.append(" ".join(words[start:end]))
        start += size - overlap
    return chunks


def fallback_response(user_message: str) -> str:
    """Static fallback when the AI service is unavailable."""
    msg = user_message.lower()
    if any(w in msg for w in ["hello", "hi", "hey"]):
        return (
            "Hello! I'm Lamla AI Tutor. I'm here to help with platform questions, "
            "study tips, and general topics. What would you like to know today?"
        )
    if any(w in msg for w in ["feature", "quiz", "flashcard"]):
        return (
            "Lamla AI offers quiz generation, flashcard creation, performance tracking, "
            "and study material uploads (PDF, PPTX, DOCX). "
            "Visit https://lamla-ai.vercel.app to explore all features."
        )
    if any(w in msg for w in ["contact", "support", "email"]):
        return (
            "You can reach the Lamla team at lamlaaiteam@gmail.com "
            "or WhatsApp +233509341251. We usually respond within 24 hours."
        )
    if any(w in msg for w in ["thank", "thanks"]):
        return "You're welcome! Let me know if you have any other questions."
    return (
        "I'm Lamla AI Tutor. I can help with platform navigation, study tools, "
        "and general questions. What would you like to know?"
    )


def _fetch_user_performance_sync(user) -> dict | None:
    """
    Fetch full performance snapshot for authenticated user.
    Returns None if user has no quiz history.
    Sends all topics (no minimum threshold) + recent quiz sessions so the AI
    can discuss results the user just took, not just long-term aggregates.
    """
    try:
        from django.db.models import Avg, Count
        from django.utils import timezone
        from apps.quiz.models import QuizSession, TopicPerformance, QuizTopicSchedule

        agg = QuizSession.objects.filter(user=user).aggregate(
            total=Count("id"), avg_score=Avg("score_percentage")
        )
        total_quizzes = agg["total"] or 0
        if total_quizzes == 0:
            return None

        avg_score = round(float(agg["avg_score"] or 0), 1)

        # All topics sorted weakest-first — no minimum so a brand-new quiz shows up immediately
        all_topics = list(
            TopicPerformance.objects.filter(user=user)
            .order_by("accuracy")
            .values_list("topic", "accuracy", "total_questions")
        )

        # Last 5 quiz sessions so the AI knows about very recent results
        recent = list(
            QuizSession.objects.filter(user=user)
            .order_by("-created_at")[:5]
            .values("subject", "score_percentage", "correct_answers", "total_questions")
        )

        due = list(
            QuizTopicSchedule.objects.filter(user=user, next_review__lte=timezone.now())
            .order_by("next_review")[:5]
            .values_list("topic", flat=True)
        )

        return {
            "total_quizzes": total_quizzes,
            "avg_score": avg_score,
            "all_topics": [(t, round(float(a), 1), q) for t, a, q in all_topics],
            "recent_quizzes": [
                {
                    "subject": r["subject"],
                    "score": round(float(r["score_percentage"]), 1),
                    "correct": r["correct_answers"],
                    "total": r["total_questions"],
                }
                for r in recent
            ],
            "due_topics": due,
        }
    except Exception:
        logger.exception("Failed to fetch user performance for chatbot")
        return None
