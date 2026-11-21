from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.quiz.models import QuizSession, QuizTopicSchedule, TopicPerformance


class BackfillTopicPerformanceCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="backfill@example.com", username="backfill"
        )
        QuizSession.objects.create(
            user=self.user,
            subject="Biology",
            total_questions=10,
            correct_answers=8,
            score_percentage=80,
        )
        QuizSession.objects.create(
            user=self.user,
            subject="Biology",
            total_questions=10,
            correct_answers=6,
            score_percentage=60,
        )
        QuizSession.objects.create(
            user=self.user,
            subject="Chemistry",
            total_questions=5,
            correct_answers=5,
            score_percentage=100,
        )

    def test_dry_run_does_not_write(self):
        out = StringIO()

        call_command("backfill_topic_performance", "--dry-run", stdout=out)

        self.assertFalse(TopicPerformance.objects.exists())
        self.assertFalse(QuizTopicSchedule.objects.exists())
        self.assertIn("Dry run", out.getvalue())

    def test_backfills_aggregates(self):
        out = StringIO()

        call_command("backfill_topic_performance", stdout=out)

        biology = TopicPerformance.objects.get(user=self.user, topic="Biology")
        self.assertEqual(biology.total_questions, 20)
        self.assertEqual(biology.correct_answers, 14)
        self.assertEqual(biology.accuracy, 70.0)

        chemistry = TopicPerformance.objects.get(user=self.user, topic="Chemistry")
        self.assertEqual(chemistry.total_questions, 5)
        self.assertEqual(chemistry.accuracy, 100.0)

        self.assertEqual(QuizTopicSchedule.objects.filter(user=self.user).count(), 2)
        self.assertIn("QuizTopicSchedule: 2 initialised", out.getvalue())

    def test_rerun_is_idempotent(self):
        call_command("backfill_topic_performance", stdout=StringIO())
        call_command("backfill_topic_performance", stdout=StringIO())

        biology = TopicPerformance.objects.get(user=self.user, topic="Biology")
        self.assertEqual(biology.total_questions, 20)
        self.assertEqual(TopicPerformance.objects.count(), 2)
        self.assertEqual(QuizTopicSchedule.objects.count(), 2)