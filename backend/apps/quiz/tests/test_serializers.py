from django.test import SimpleTestCase

from apps.quiz.serializers import (
    QuizGenerateRequestSerializer,
    QuizSubmitRequestSerializer,
    QuizYouTubeRequestSerializer,
)


class QuizGenerateRequestSerializerTests(SimpleTestCase):
    def test_defaults_are_applied(self):
        serializer = QuizGenerateRequestSerializer(data={})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["subject"], "General")
        self.assertEqual(serializer.validated_data["extractedText"], "")
        self.assertEqual(serializer.validated_data["num_mcq"], 7)
        self.assertEqual(serializer.validated_data["num_short"], 0)
        self.assertEqual(serializer.validated_data["difficulty"], "medium")
        self.assertEqual(serializer.validated_data["source_type"], "text")
        self.assertEqual(serializer.validated_data["source_filename"], "")
        self.assertEqual(serializer.validated_data["quiz_time"], 10)

    def test_allows_zero_mcq_when_short_questions_exist(self):
        serializer = QuizGenerateRequestSerializer(data={"num_mcq": 0, "num_short": 3})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["num_mcq"], 0)

    def test_rejects_mcq_above_thirty(self):
        serializer = QuizGenerateRequestSerializer(data={"num_mcq": 31})

        self.assertFalse(serializer.is_valid())
        self.assertIn("num_mcq", serializer.errors)

    def test_rejects_negative_short_questions(self):
        serializer = QuizGenerateRequestSerializer(data={"num_short": -1})

        self.assertFalse(serializer.is_valid())
        self.assertIn("num_short", serializer.errors)

    def test_rejects_quiz_time_outside_one_to_180(self):
        self.assertFalse(QuizGenerateRequestSerializer(data={"quiz_time": 0}).is_valid())
        self.assertFalse(QuizGenerateRequestSerializer(data={"quiz_time": 181}).is_valid())

    def test_coerces_numeric_strings(self):
        serializer = QuizGenerateRequestSerializer(data={"num_mcq": "5", "quiz_time": "20"})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["num_mcq"], 5)
        self.assertEqual(serializer.validated_data["quiz_time"], 20)


class QuizSubmitRequestSerializerTests(SimpleTestCase):
    def test_requires_quiz_data(self):
        serializer = QuizSubmitRequestSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertIn("quiz_data", serializer.errors)

    def test_applies_defaults(self):
        serializer = QuizSubmitRequestSerializer(data={"quiz_data": {"mcq_questions": []}})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["user_answers"], {})
        self.assertIsNone(serializer.validated_data["quiz_id"])
        self.assertEqual(serializer.validated_data["duration_minutes"], 0)
        self.assertEqual(serializer.validated_data["time_limit"], 0)
        self.assertFalse(serializer.validated_data["exam_mode"])

    def test_rejects_non_dict_quiz_data(self):
        serializer = QuizSubmitRequestSerializer(data={"quiz_data": []})

        self.assertFalse(serializer.is_valid())
        self.assertIn("quiz_data", serializer.errors)


class QuizYouTubeRequestSerializerTests(SimpleTestCase):
    def test_accepts_youtube_url(self):
        serializer = QuizYouTubeRequestSerializer(data={"url": "https://youtu.be/dQw4w9WgXcQ"})

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_non_url(self):
        serializer = QuizYouTubeRequestSerializer(data={"url": "not a url"})

        self.assertFalse(serializer.is_valid())
        self.assertIn("url", serializer.errors)

    def test_requires_url(self):
        serializer = QuizYouTubeRequestSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertIn("url", serializer.errors)