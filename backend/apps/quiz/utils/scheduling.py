"""Topic-performance and spaced-repetition updates for quiz submissions."""

import logging

from asgiref.sync import sync_to_async
from django.db.models import F

from apps.flashcards.scheduling import update_sm2
from apps.quiz.models import QuizTopicSchedule, TopicPerformance
from apps.quiz.utils.scoring import score_to_sm2_quality

logger = logging.getLogger(__name__)


def _update_topic_performance_sync(user, topic: str, correct: int, total: int) -> None:
    topic_performance, created = TopicPerformance.objects.get_or_create(
        user=user,
        topic=topic,
        defaults={
            "subject": topic,
            "total_questions": total,
            "correct_answers": correct,
            "accuracy": round(correct / total * 100, 2) if total > 0 else 0.0,
        },
    )
    if not created:
        topic_performance.total_questions = F("total_questions") + total
        topic_performance.correct_answers = F("correct_answers") + correct
        topic_performance.save(update_fields=["total_questions", "correct_answers"])
        topic_performance.refresh_from_db(fields=["total_questions", "correct_answers"])
        topic_performance.accuracy = (
            round(topic_performance.correct_answers / topic_performance.total_questions * 100, 2)
            if topic_performance.total_questions > 0
            else 0.0
        )
        topic_performance.save(update_fields=["accuracy"])


def _update_quiz_schedule_sync(user, topic: str, score_percent: float) -> None:
    schedule, _ = QuizTopicSchedule.objects.get_or_create(
        user=user,
        topic=topic,
        defaults={"subject": topic},
    )
    update_sm2(schedule, score_to_sm2_quality(score_percent))


async def update_topic_performance(user, topic: str, correct: int, total: int) -> None:
    await sync_to_async(_update_topic_performance_sync, thread_sensitive=True)(user, topic, correct, total)


async def update_quiz_schedule(user, topic: str, score_percent: float) -> None:
    await sync_to_async(_update_quiz_schedule_sync, thread_sensitive=True)(user, topic, score_percent)
