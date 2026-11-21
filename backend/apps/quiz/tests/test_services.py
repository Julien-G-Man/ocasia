import json
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.core.ai_engine import APIIntegrationError
from apps.quiz.models import QuizSession, QuizTopicSchedule, TopicPerformance
from apps.quiz.services import (
    QuizGenerationError,
    _parse_response,
    evaluate_short_answer,
    generate_quiz,
    get_replay,
    list_due_topics,
    list_history,
    list_weak_areas,
    normalize_study_text,
    submit_quiz,
)

STUDY_TEXT = "Photosynthesis converts light energy into chemical energy in plants."


def _mcq(index=0, answer="A"):
    return {
        "question": f"Question {index}?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "answer": answer,
        "explanation": f"Explanation {index}",
    }


class NormalizeStudyTextTests(SimpleTestCase):
    def test_non_string_returns_empty(self):
        self.assertEqual(normalize_study_text(None), "")
        self.assertEqual(normalize_study_text(123), "")

    def test_normalizes_unicode_compatibility(self):
        self.assertEqual(normalize_study_text("ＡＢＣ"), "ABC")
        self.assertEqual(normalize_study_text("ﬁne ﬂat"), "fine flat")

    def test_replaces_dashes_and_math_symbols(self):
        self.assertEqual(normalize_study_text("a\u2013b\u2014c\u2212d"), "a-b-c-d")
        self.assertEqual(normalize_study_text("2\u00d73"), "2 x 3")
        self.assertEqual(normalize_study_text("6\u00f72"), "6 / 2")

    def test_removes_soft_hyphen_and_zero_width(self):
        self.assertEqual(normalize_study_text("co\u00adoperate\u200b"), "cooperate")

    def test_collapses_whitespace(self):
        self.assertEqual(normalize_study_text("a \t\t b"), "a b")
        self.assertEqual(normalize_study_text("a\n\n\n\nb"), "a\n\nb")

    def test_truncates_to_max_chars(self):
        self.assertEqual(normalize_study_text("abcdef", max_chars=3), "abc")

    def test_strips_outer_whitespace(self):
        self.assertEqual(normalize_study_text("  hello  "), "hello")


class ParseResponseTests(SimpleTestCase):
    def test_dict_passthrough(self):
        data = {"a": 1}
        self.assertIs(_parse_response(data), data)

    def test_list_passthrough(self):
        data = [1, 2]
        self.assertIs(_parse_response(data), data)

    def test_fenced_json(self):
        self.assertEqual(_parse_response('```json\n{"a": 1}\n```'), {"a": 1})

    def test_json_with_surrounding_prose(self):
        self.assertEqual(_parse_response('Here you go: {"a": 1} thanks'), {"a": 1})

    def test_invalid_returns_none(self):
        self.assertIsNone(_parse_response("not json"))


class GenerateQuizTests(SimpleTestCase):
    @patch("apps.quiz.services.record_ai_latency", new_callable=AsyncMock)
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_normalizes_and_returns_quiz(self, generate_text, record_latency):
        generate_text.return_value = json.dumps(
            {
                "mcq_questions": [_mcq(answer="a")],
                "short_questions": [
                    {"question": "What converts light?", "answer": "Photosynthesis"}
                ],
            }
        )

        result = await generate_quiz(
            subject="Biology", study_text=STUDY_TEXT, num_mcq=1, num_short=1
        )

        self.assertEqual(result["subject"], "Biology")
        self.assertEqual(result["study_text"], STUDY_TEXT)
        self.assertEqual(result["difficulty"], "medium")
        self.assertEqual(result["mcq_questions"][0]["answer"], "A")
        self.assertEqual(result["mcq_questions"][0]["type"], "mcq")
        self.assertEqual(result["short_questions"][0]["type"], "short")
        self.assertEqual(result["short_questions"][0]["options"], [])
        record_latency.assert_awaited_once()
        self.assertEqual(record_latency.await_args.args[0], "quiz")

    @patch("apps.quiz.services.record_ai_latency", new_callable=AsyncMock)
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_truncates_long_study_text(self, generate_text, record_latency):
        generate_text.return_value = json.dumps(
            {"mcq_questions": [_mcq()], "short_questions": []}
        )

        result = await generate_quiz(
            subject="Biology",
            study_text="x" * 20_000,
            num_mcq=1,
            num_short=0,
        )

        self.assertEqual(len(result["study_text"]), 16_000)
        self.assertIn("x" * 16_000, generate_text.await_args.args[0])

    @patch("apps.quiz.services.record_ai_latency", new_callable=AsyncMock)
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_caps_question_counts(self, generate_text, record_latency):
        generate_text.return_value = json.dumps(
            {
                "mcq_questions": [_mcq(index) for index in range(40)],
                "short_questions": [
                    {"question": f"Short {index}?", "answer": "Answer"}
                    for index in range(20)
                ],
            }
        )

        result = await generate_quiz(
            subject="Biology", study_text=STUDY_TEXT, num_mcq=99, num_short=99
        )

        self.assertEqual(len(result["mcq_questions"]), 30)
        self.assertEqual(len(result["short_questions"]), 10)
        self.assertGreaterEqual(generate_text.await_args.kwargs["max_tokens"], 4096)
        self.assertLessEqual(generate_text.await_args.kwargs["max_tokens"], 8192)

    @patch("apps.quiz.services.record_ai_latency", new_callable=AsyncMock)
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_random_difficulty_resolves_to_allowed_level(
        self, generate_text, record_latency
    ):
        generate_text.return_value = json.dumps(
            {"mcq_questions": [_mcq()], "short_questions": []}
        )

        result = await generate_quiz(
            subject="Biology",
            study_text=STUDY_TEXT,
            difficulty="random",
            num_mcq=1,
            num_short=0,
        )

        self.assertIn(result["difficulty"], {"easy", "medium", "hard"})
        self.assertIn(
            f"Difficulty: {result['difficulty']}", generate_text.await_args.args[0]
        )

    @patch("apps.quiz.services.record_ai_latency", new_callable=AsyncMock)
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_unknown_difficulty_falls_back_to_medium(
        self, generate_text, record_latency
    ):
        generate_text.return_value = json.dumps(
            {"mcq_questions": [_mcq()], "short_questions": []}
        )

        result = await generate_quiz(
            subject="Biology",
            study_text=STUDY_TEXT,
            difficulty="extreme",
            num_mcq=1,
            num_short=0,
        )

        self.assertEqual(result["difficulty"], "medium")

    @patch("apps.quiz.services.record_ai_latency", new_callable=AsyncMock)
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_unknown_source_type_falls_back_to_text(
        self, generate_text, record_latency
    ):
        generate_text.return_value = json.dumps(
            {"mcq_questions": [_mcq()], "short_questions": []}
        )

        await generate_quiz(
            subject="Biology",
            study_text=STUDY_TEXT,
            num_mcq=1,
            num_short=0,
            source_type="video",
        )

        self.assertIn("typed or pasted", generate_text.await_args.args[0])

    @patch("apps.quiz.services.record_ai_latency", new_callable=AsyncMock)
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_wraps_list_response(self, generate_text, record_latency):
        generate_text.return_value = json.dumps([_mcq()])

        result = await generate_quiz(
            subject="Biology", study_text=STUDY_TEXT, num_mcq=1, num_short=0
        )

        self.assertEqual(len(result["mcq_questions"]), 1)
        self.assertEqual(result["short_questions"], [])

    @patch("apps.quiz.services.record_ai_latency", new_callable=AsyncMock)
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_repairs_malformed_json_once(self, generate_text, record_latency):
        generate_text.side_effect = [
            "not json",
            json.dumps({"mcq_questions": [_mcq()], "short_questions": []}),
        ]

        result = await generate_quiz(
            subject="Biology", study_text=STUDY_TEXT, num_mcq=1, num_short=0
        )

        self.assertEqual(len(result["mcq_questions"]), 1)
        self.assertEqual(generate_text.await_count, 2)

    @patch("apps.quiz.services.record_ai_latency", new_callable=AsyncMock)
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_raises_after_failed_repair(self, generate_text, record_latency):
        generate_text.side_effect = ["not json", "still not json"]

        with self.assertRaises(QuizGenerationError):
            await generate_quiz(
                subject="Biology", study_text=STUDY_TEXT, num_mcq=1, num_short=0
            )

        self.assertEqual(generate_text.await_count, 2)

    @patch("apps.quiz.services.record_ai_latency", new_callable=AsyncMock)
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_rejects_non_list_question_sections(
        self, generate_text, record_latency
    ):
        generate_text.return_value = json.dumps(
            {"mcq_questions": {}, "short_questions": []}
        )

        with self.assertRaises(QuizGenerationError):
            await generate_quiz(
                subject="Biology", study_text=STUDY_TEXT, num_mcq=1, num_short=0
            )

    @patch("apps.quiz.services.record_ai_latency", new_callable=AsyncMock)
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_rejects_empty_question_sections(self, generate_text, record_latency):
        generate_text.return_value = json.dumps(
            {"mcq_questions": [], "short_questions": []}
        )

        with self.assertRaises(QuizGenerationError):
            await generate_quiz(
                subject="Biology", study_text=STUDY_TEXT, num_mcq=1, num_short=0
            )

    @patch("apps.quiz.services.record_ai_latency", new_callable=AsyncMock)
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_propagates_provider_errors(self, generate_text, record_latency):
        generate_text.side_effect = APIIntegrationError("provider down")

        with self.assertRaises(APIIntegrationError):
            await generate_quiz(
                subject="Biology", study_text=STUDY_TEXT, num_mcq=1, num_short=0
            )

    @patch("apps.quiz.services.record_ai_latency", new_callable=AsyncMock)
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_requires_subject(self, generate_text, record_latency):
        with self.assertRaisesMessage(ValueError, "Subject is required"):
            await generate_quiz(
                subject="   ", study_text=STUDY_TEXT, num_mcq=1, num_short=0
            )

        generate_text.assert_not_awaited()

    @patch("apps.quiz.services.record_ai_latency", new_callable=AsyncMock)
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_requires_minimum_study_text(self, generate_text, record_latency):
        with self.assertRaisesMessage(ValueError, "at least 30 characters"):
            await generate_quiz(
                subject="Biology", study_text="short", num_mcq=1, num_short=0
            )

        generate_text.assert_not_awaited()

    @patch("apps.quiz.services.record_ai_latency", new_callable=AsyncMock)
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_requires_at_least_one_question(self, generate_text, record_latency):
        with self.assertRaisesMessage(ValueError, "at least one quiz question"):
            await generate_quiz(
                subject="Biology", study_text=STUDY_TEXT, num_mcq=0, num_short=0
            )

        generate_text.assert_not_awaited()

    @patch("apps.quiz.services.record_ai_latency", new_callable=AsyncMock)
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_rejects_non_integer_counts(self, generate_text, record_latency):
        with self.assertRaisesMessage(ValueError, "must be integers"):
            await generate_quiz(
                subject="Biology",
                study_text=STUDY_TEXT,
                num_mcq="many",
                num_short=0,
            )


class EvaluateShortAnswerTests(SimpleTestCase):
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_empty_answer_short_circuits(self, generate_text):
        result = await evaluate_short_answer("Q?", "A", "   ")

        self.assertFalse(result["is_correct"])
        self.assertEqual(result["score"], 0.0)
        generate_text.assert_not_awaited()

    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_parses_evaluator_json(self, generate_text):
        generate_text.return_value = json.dumps(
            {"is_correct": True, "score": 0.9, "reasoning": "Close enough."}
        )

        result = await evaluate_short_answer("Q?", "A", "a")

        self.assertTrue(result["is_correct"])
        self.assertEqual(result["score"], 0.9)
        self.assertEqual(result["reasoning"], "Close enough.")
        prompt = generate_text.await_args.args[0]
        self.assertIn("Q?", prompt)
        self.assertIn("A", prompt)
        self.assertIn("a", prompt)

    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_clamps_score(self, generate_text):
        generate_text.return_value = json.dumps({"score": 5})

        result = await evaluate_short_answer("Q?", "A", "a")

        self.assertEqual(result["score"], 1.0)

    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_defaults_is_correct_from_score(self, generate_text):
        generate_text.return_value = json.dumps({"score": 0.85})

        result = await evaluate_short_answer("Q?", "A", "a")

        self.assertTrue(result["is_correct"])

    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_falls_back_to_exact_match_on_failure(self, generate_text):
        generate_text.side_effect = RuntimeError("provider down")

        result = await evaluate_short_answer("Q?", "Photosynthesis", "photosynthesis")

        self.assertTrue(result["is_correct"])
        self.assertEqual(result["score"], 1.0)
        self.assertIn("fallback", result["reasoning"])

    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_falls_back_to_incorrect_on_mismatch(self, generate_text):
        generate_text.side_effect = RuntimeError("provider down")

        result = await evaluate_short_answer("Q?", "Photosynthesis", "respiration")

        self.assertFalse(result["is_correct"])
        self.assertEqual(result["score"], 0.0)

    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_invalid_json_falls_back(self, generate_text):
        generate_text.return_value = "not json"

        result = await evaluate_short_answer("Q?", "Photosynthesis", "photosynthesis")

        self.assertTrue(result["is_correct"])


class SubmitQuizTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="quiz@example.com", username="quiz"
        )

    def _submit(self, quiz_data, answers, **kwargs):
        from asgiref.sync import async_to_sync

        return async_to_sync(submit_quiz)(
            user=self.user,
            quiz_data=quiz_data,
            user_answers=answers,
            **kwargs,
        )

    @patch("apps.quiz.services.update_quiz_schedule", new_callable=AsyncMock)
    @patch("apps.quiz.services.update_topic_performance", new_callable=AsyncMock)
    def test_scores_mcq_and_persists_session(self, update_performance, update_schedule):
        quiz_data = {
            "subject": "Biology",
            "difficulty": "medium",
            "mcq_questions": [
                {
                    "question": "Q1",
                    "options": ["a", "b"],
                    "answer": "A",
                    "explanation": "E1",
                    "type": "mcq",
                },
                {
                    "question": "Q2",
                    "options": ["c", "d"],
                    "answer": "B",
                    "explanation": "E2",
                    "type": "mcq",
                },
            ],
            "short_questions": [],
        }

        results = self._submit(
            quiz_data,
            {"0": "a", "1": "b"},
            quiz_id="qid",
            duration_minutes=5,
            time_limit=10,
            exam_mode=True,
        )

        self.assertEqual(results["score"], 2)
        self.assertEqual(results["total"], 2)
        self.assertEqual(results["score_percent"], 100.0)
        self.assertEqual(results["quiz_id"], "qid")
        self.assertEqual(results["details"][0]["user_answer_display"], "A. a")
        self.assertEqual(results["details"][1]["user_answer_display"], "B. d")

        session = QuizSession.objects.get(user=self.user)
        self.assertEqual(session.subject, "Biology")
        self.assertEqual(session.total_questions, 2)
        self.assertEqual(session.correct_answers, 2)
        self.assertEqual(float(session.score_percentage), 100.0)
        self.assertTrue(session.exam_mode)
        self.assertEqual(session.time_limit_minutes, 10)
        self.assertEqual(session.duration_minutes, 5)
        self.assertEqual(session.questions_data, quiz_data)
        self.assertEqual(session.user_answers, {"0": "a", "1": "b"})

        update_performance.assert_awaited_once()
        update_schedule.assert_awaited_once()

    @patch("apps.quiz.services.update_quiz_schedule", new_callable=AsyncMock)
    @patch("apps.quiz.services.update_topic_performance", new_callable=AsyncMock)
    @patch("apps.quiz.services.evaluate_short_answer", new_callable=AsyncMock)
    def test_short_answer_uses_evaluator(
        self, evaluate, update_performance, update_schedule
    ):
        evaluate.return_value = {"is_correct": True, "score": 1.0, "reasoning": "Good."}
        quiz_data = {
            "subject": "Biology",
            "mcq_questions": [],
            "short_questions": [
                {"question": "Q?", "answer": "Photosynthesis", "explanation": "E"}
            ],
        }

        results = self._submit(quiz_data, {"0": "photosynthesis"})

        self.assertEqual(results["score"], 1)
        self.assertEqual(results["details"][0]["reasoning"], "Good.")
        evaluate.assert_awaited_once_with("Q?", "Photosynthesis", "photosynthesis")

    def test_rejects_quiz_without_questions(self):
        with self.assertRaisesMessage(ValueError, "No questions found"):
            self._submit(
                {"subject": "Biology", "mcq_questions": [], "short_questions": []}, {}
            )

    @patch("apps.quiz.services.update_quiz_schedule", new_callable=AsyncMock)
    @patch("apps.quiz.services.update_topic_performance", new_callable=AsyncMock)
    def test_busts_quiz_caches(self, update_performance, update_schedule):
        uid = self.user.id
        keys = [
            f"quiz:hist:{uid}",
            f"quiz:weak:{uid}",
            f"quiz:due:{uid}",
            f"dash:stats:{uid}",
            "admin:stats",
        ]
        for key in keys:
            cache.set(key, {"cached": True}, 60)

        self._submit(
            {
                "subject": "Biology",
                "mcq_questions": [_mcq()],
                "short_questions": [],
            },
            {"0": "A"},
        )

        for key in keys:
            self.assertIsNone(cache.get(key), key)

    def test_updates_topic_performance_and_schedule(self):
        self._submit(
            {
                "subject": "Biology",
                "difficulty": "medium",
                "mcq_questions": [_mcq()],
                "short_questions": [],
            },
            {"0": "A"},
        )

        performance = TopicPerformance.objects.get(user=self.user, topic="Biology")
        self.assertEqual(performance.total_questions, 1)
        self.assertEqual(performance.correct_answers, 1)
        self.assertEqual(performance.accuracy, 100.0)

        schedule = QuizTopicSchedule.objects.get(user=self.user, topic="Biology")
        self.assertEqual(schedule.repetition, 1)


class QuizHistoryServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="history@example.com", username="history"
        )
        self.other = User.objects.create_user(
            email="other@example.com", username="other"
        )

    def test_returns_only_own_sessions_newest_first(self):
        old = QuizSession.objects.create(
            user=self.user, subject="Old", total_questions=1, correct_answers=1
        )
        new = QuizSession.objects.create(
            user=self.user,
            subject="New",
            total_questions=2,
            correct_answers=1,
            score_percentage=50,
        )
        QuizSession.objects.filter(pk=new.pk).update(
            created_at=old.created_at + timedelta(seconds=1)
        )
        QuizSession.objects.create(user=self.other, subject="Other")

        result = list_history(self.user)

        self.assertEqual(
            [item["subject"] for item in result["history"]], ["New", "Old"]
        )
        self.assertEqual(result["history"][0]["score_percent"], 50.0)

    def test_caches_result(self):
        QuizSession.objects.create(user=self.user, subject="First")
        first = list_history(self.user)

        QuizSession.objects.create(user=self.user, subject="Second")
        second = list_history(self.user)

        self.assertEqual(first, second)

        cache.delete(f"quiz:hist:{self.user.id}")
        third = list_history(self.user)
        self.assertEqual(
            [item["subject"] for item in third["history"]], ["Second", "First"]
        )


class QuizReplayServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="replay@example.com", username="replay"
        )
        self.other = User.objects.create_user(
            email="other@example.com", username="other"
        )

    def test_returns_stored_quiz_data(self):
        session = QuizSession.objects.create(
            user=self.user, questions_data={"mcq_questions": []}
        )

        self.assertEqual(
            get_replay(self.user, session.id),
            {"quiz_data": {"mcq_questions": []}},
        )

    def test_hides_other_users_session(self):
        session = QuizSession.objects.create(user=self.other, questions_data={})

        with self.assertRaises(QuizSession.DoesNotExist):
            get_replay(self.user, session.id)


class QuizWeakAreasServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="weak@example.com", username="weak"
        )
        self.other = User.objects.create_user(
            email="other@example.com", username="other"
        )

    def test_returns_lowest_accuracy_with_min_three_questions(self):
        TopicPerformance.objects.create(
            user=self.user,
            topic="Strong",
            subject="Strong",
            total_questions=5,
            correct_answers=5,
            accuracy=100,
        )
        TopicPerformance.objects.create(
            user=self.user,
            topic="Weak",
            subject="Weak",
            total_questions=5,
            correct_answers=1,
            accuracy=20,
        )
        TopicPerformance.objects.create(
            user=self.user,
            topic="TooFew",
            subject="TooFew",
            total_questions=2,
            correct_answers=0,
            accuracy=0,
        )
        TopicPerformance.objects.create(
            user=self.other,
            topic="OtherWeak",
            subject="OtherWeak",
            total_questions=5,
            correct_answers=0,
            accuracy=0,
        )

        result = list_weak_areas(self.user)

        self.assertEqual(
            [item["topic"] for item in result["weak_areas"]], ["Weak", "Strong"]
        )
        self.assertEqual(result["weak_areas"][0]["accuracy"], 20.0)

    def test_caps_at_five(self):
        for index in range(6):
            TopicPerformance.objects.create(
                user=self.user,
                topic=f"T{index}",
                subject=f"T{index}",
                total_questions=5,
                correct_answers=5 - index,
                accuracy=(index + 1) * 10,
            )

        result = list_weak_areas(self.user)

        self.assertEqual(
            [item["topic"] for item in result["weak_areas"]],
            ["T0", "T1", "T2", "T3", "T4"],
        )


class QuizDueTopicsServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="due@example.com", username="due"
        )
        self.other = User.objects.create_user(
            email="other@example.com", username="other"
        )

    def test_returns_only_due_topics_ordered_by_review(self):
        now = timezone.now()
        QuizTopicSchedule.objects.create(
            user=self.user,
            topic="Overdue",
            subject="Overdue",
            next_review=now - timedelta(days=2),
        )
        QuizTopicSchedule.objects.create(
            user=self.user,
            topic="Future",
            subject="Future",
            next_review=now + timedelta(days=2),
        )
        QuizTopicSchedule.objects.create(
            user=self.other,
            topic="OtherDue",
            subject="OtherDue",
            next_review=now - timedelta(days=1),
        )

        result = list_due_topics(self.user)

        self.assertEqual(
            [item["topic"] for item in result["due_topics"]], ["Overdue"]
        )
        self.assertIsNone(result["due_topics"][0]["last_review"])

    def test_caches_result(self):
        now = timezone.now()
        QuizTopicSchedule.objects.create(
            user=self.user,
            topic="Overdue",
            subject="Overdue",
            next_review=now - timedelta(days=1),
        )
        first = list_due_topics(self.user)

        QuizTopicSchedule.objects.create(
            user=self.user,
            topic="AlsoOverdue",
            subject="AlsoOverdue",
            next_review=now - timedelta(hours=1),
        )
        second = list_due_topics(self.user)

        self.assertEqual(first, second)

        cache.delete(f"quiz:due:{self.user.id}")
        third = list_due_topics(self.user)
        self.assertEqual(
            [item["topic"] for item in third["due_topics"]],
            ["Overdue", "AlsoOverdue"],
        )