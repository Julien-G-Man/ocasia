"""Agent tool for fetching the student's live learning performance."""

import logging

from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


def _load_performance(user_id: int) -> tuple[bool, dict | None]:
    """Aggregate the student's quiz performance in a worker thread.

    Self-contained so the tutor app no longer depends on the retired chatbot app.
    Returns ``(user_found, snapshot)`` where ``snapshot`` is ``None`` when the
    user has no quiz history yet.
    """
    from django.contrib.auth import get_user_model
    from django.db.models import Avg, Count
    from django.utils import timezone

    from apps.quiz.models import QuizSession, TopicPerformance, QuizTopicSchedule

    user = get_user_model().objects.filter(id=user_id).first()
    if user is None:
        return False, None

    agg = QuizSession.objects.filter(user=user).aggregate(
        total=Count("id"), avg_score=Avg("score_percentage")
    )
    total_quizzes = agg["total"] or 0
    if total_quizzes == 0:
        return True, None

    avg_score = round(float(agg["avg_score"] or 0), 1)

    # All topics sorted weakest-first so a brand-new quiz shows up immediately.
    all_topics = list(
        TopicPerformance.objects.filter(user=user)
        .order_by("accuracy")
        .values_list("topic", "accuracy", "total_questions")
    )

    # Last 5 quiz sessions so the agent knows about very recent results.
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

    return True, {
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


async def get_user_performance(user_id: int | None = None) -> dict:
    """Fetch the signed-in student's live quiz performance snapshot.

    Returns the average score, per-topic accuracy (weakest first), the most
    recent quiz sessions, and topics due for review. Requires an authenticated
    student; the runner injects the authenticated ``user_id``.
    """
    if not user_id:
        return {
            "available": False,
            "message": "Performance is only available for signed-in students.",
        }

    try:
        found, performance = await sync_to_async(
            _load_performance, thread_sensitive=True
        )(user_id)
    except Exception as exc:
        logger.exception("Tutor performance tool failed for user_id=%s", user_id)
        return {"available": False, "error": str(exc)}

    if not found:
        return {"available": False, "message": "Student account was not found."}
    if performance is None:
        return {
            "available": True,
            "total_quizzes": 0,
            "message": "No quiz attempts yet. Encourage the student to take a first quiz.",
        }
    return {"available": True, **performance}