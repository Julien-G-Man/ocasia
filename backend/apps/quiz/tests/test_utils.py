import io
import unittest
from unittest.mock import AsyncMock, patch

from django.test import SimpleTestCase, TestCase

from apps.quiz.utils.download_helpers import HAS_REPORTLAB, build_download
from apps.quiz.utils.extract_text import extract_file_text
from apps.quiz.utils.scoring import format_mcq_answer, score_to_sm2_quality
from apps.quiz.utils.youtube_api import extract_video_id, fetch_youtube_quiz_content


class FakeUpload:
    def __init__(self, name, payload=b""):
        self.name = name
        self._payload = payload
        self.seek_calls = 0

    def seek(self, _offset):
        self.seek_calls += 1

    def read(self):
        return self._payload


class FormatMcqAnswerTests(SimpleTestCase):
    def test_letter_with_options(self):
        self.assertEqual(format_mcq_answer("A", ["one", "two"]), "A. one")
        self.assertEqual(format_mcq_answer("b", ["one", "two"]), "B. two")

    def test_letter_without_options(self):
        self.assertEqual(format_mcq_answer("B", []), "B")

    def test_empty_answer(self):
        self.assertEqual(format_mcq_answer("", ["one"]), "")

    def test_out_of_range_letter(self):
        self.assertEqual(format_mcq_answer("Z", ["one"]), "Z")

    def test_matches_option_text_case_insensitively(self):
        self.assertEqual(format_mcq_answer("two", ["one", "two"]), "B. two")

    def test_unknown_text_returns_normalized_value(self):
        self.assertEqual(format_mcq_answer("  three  ", ["one"]), "three")


class ScoreToSm2QualityTests(SimpleTestCase):
    def test_boundaries(self):
        cases = [
            (100, 5),
            (90, 5),
            (89.9, 4),
            (75, 4),
            (74.9, 3),
            (60, 3),
            (59.9, 2),
            (40, 2),
            (39.9, 1),
            (20, 1),
            (19.9, 0),
            (0, 0),
        ]
        for score, expected in cases:
            with self.subTest(score=score):
                self.assertEqual(score_to_sm2_quality(score), expected)


class ExtractFileTextTests(SimpleTestCase):
    def test_reads_plain_text(self):
        upload = FakeUpload("notes.txt", b"Photosynthesis converts light.")

        self.assertEqual(extract_file_text(upload), "Photosynthesis converts light.")
        self.assertGreaterEqual(upload.seek_calls, 1)

    def test_strips_surrounding_whitespace(self):
        upload = FakeUpload("notes.txt", b"  hello  \n")

        self.assertEqual(extract_file_text(upload), "hello")

    def test_empty_text_returns_empty_string(self):
        self.assertEqual(extract_file_text(FakeUpload("empty.txt", b"")), "")

    def test_unsupported_extension_raises_value_error(self):
        with self.assertRaisesMessage(ValueError, "Unsupported file format: .csv"):
            extract_file_text(FakeUpload("data.csv", b"a,b"))

    def test_missing_extension_is_unsupported(self):
        with self.assertRaisesMessage(ValueError, "Unsupported file format: "):
            extract_file_text(FakeUpload("noext", b"data"))


class BuildDownloadTests(SimpleTestCase):
    RESULTS = {
        "subject": "Biology",
        "difficulty": "medium",
        "source_filename": "notes.pdf",
        "details": [
            {
                "question": "What absorbs light?",
                "options": ["Chlorophyll", "Water", "Oxygen", "Heat"],
                "correct_answer": "A",
                "explanation": "Chlorophyll absorbs light.",
            }
        ],
    }

    def test_builds_txt_download(self):
        content, content_type, filename = build_download(self.RESULTS, "txt")
        text = content.decode("utf-8")

        self.assertTrue(content_type.startswith("text/plain"))
        self.assertTrue(filename.endswith(".txt"))
        self.assertIn("BIOLOGY", text)
        self.assertIn("What absorbs light?", text)
        self.assertIn("Chlorophyll", text)

    def test_builds_docx_download(self):
        import docx

        content, content_type, filename = build_download(self.RESULTS, "docx")

        self.assertTrue(filename.endswith(".docx"))
        self.assertIn("wordprocessingml", content_type)
        document = docx.Document(io.BytesIO(content))
        self.assertTrue(
            any("What absorbs light?" in paragraph.text for paragraph in document.paragraphs)
        )

    @unittest.skipUnless(HAS_REPORTLAB, "reportlab is not installed")
    def test_builds_pdf_download(self):
        content, content_type, filename = build_download(self.RESULTS, "pdf")

        self.assertEqual(content_type, "application/pdf")
        self.assertTrue(filename.endswith(".pdf"))
        self.assertTrue(content.startswith(b"%PDF"))

    def test_empty_results_raise_value_error(self):
        with self.assertRaisesMessage(ValueError, "No results data provided"):
            build_download({}, "txt")

    def test_defaults_to_pdf_format(self):
        if not HAS_REPORTLAB:
            self.skipTest("reportlab is not installed")

        _, content_type, filename = build_download(self.RESULTS)

        self.assertEqual(content_type, "application/pdf")
        self.assertTrue(filename.endswith(".pdf"))


class ExtractVideoIdTests(SimpleTestCase):
    def test_watch_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_short_url(self):
        self.assertEqual(extract_video_id("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")

    def test_shorts_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_embed_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_invalid_url(self):
        self.assertIsNone(extract_video_id("https://example.com/video"))


class FetchYoutubeQuizContentTests(SimpleTestCase):
    async def test_returns_transcript_title_and_video_id(self):
        transcript = " ".join(f"word{index}" for index in range(30))

        with patch(
            "apps.quiz.utils.youtube_api._fetch_transcript_sync", return_value=transcript
        ) as fetch_transcript, patch(
            "apps.quiz.utils.youtube_api._fetch_video_title",
            new_callable=AsyncMock,
            return_value="My Video",
        ):
            result = await fetch_youtube_quiz_content("https://youtu.be/dQw4w9WgXcQ")

        self.assertEqual(result["video_id"], "dQw4w9WgXcQ")
        self.assertEqual(result["title"], "My Video")
        self.assertEqual(result["text"], transcript)
        fetch_transcript.assert_called_once_with("dQw4w9WgXcQ")

    async def test_falls_back_to_generated_title(self):
        transcript = "x" * 100

        with patch(
            "apps.quiz.utils.youtube_api._fetch_transcript_sync", return_value=transcript
        ), patch(
            "apps.quiz.utils.youtube_api._fetch_video_title",
            new_callable=AsyncMock,
            return_value="",
        ):
            result = await fetch_youtube_quiz_content("https://youtu.be/dQw4w9WgXcQ")

        self.assertEqual(result["title"], "YouTube (dQw4w9WgXcQ)")

    async def test_invalid_url_raises_value_error(self):
        with self.assertRaisesMessage(ValueError, "Could not find a YouTube video ID"):
            await fetch_youtube_quiz_content("https://example.com/")

    async def test_short_transcript_raises_value_error(self):
        with patch(
            "apps.quiz.utils.youtube_api._fetch_transcript_sync", return_value="too short"
        ), patch(
            "apps.quiz.utils.youtube_api._fetch_video_title",
            new_callable=AsyncMock,
            return_value="",
        ):
            with self.assertRaisesMessage(ValueError, "too short"):
                await fetch_youtube_quiz_content("https://youtu.be/dQw4w9WgXcQ")

    async def test_transcript_failure_is_surfaced(self):
        with patch(
            "apps.quiz.utils.youtube_api._fetch_transcript_sync",
            side_effect=ValueError("Captions are disabled."),
        ), patch(
            "apps.quiz.utils.youtube_api._fetch_video_title",
            new_callable=AsyncMock,
            return_value="",
        ):
            with self.assertRaisesMessage(ValueError, "Captions are disabled"):
                await fetch_youtube_quiz_content("https://youtu.be/dQw4w9WgXcQ")


class RecordAiLatencyTests(TestCase):
    def test_creates_latency_row(self):
        from asgiref.sync import async_to_sync

        from apps.dashboard.models import AIResponseLatency
        from apps.quiz.utils.latency import record_ai_latency

        async_to_sync(record_ai_latency)("quiz", 321)

        row = AIResponseLatency.objects.get()
        self.assertEqual(row.feature, "quiz")
        self.assertEqual(row.duration_ms, 321)


class UpdateTopicPerformanceTests(TestCase):
    def setUp(self):
        from apps.accounts.models import User

        self.user = User.objects.create_user(
            email="stats@example.com", username="stats"
        )

    def test_creates_then_accumulates(self):
        from asgiref.sync import async_to_sync

        from apps.quiz.models import TopicPerformance
        from apps.quiz.utils.scheduling import update_topic_performance

        async_to_sync(update_topic_performance)(self.user, "Biology", 3, 4)
        performance = TopicPerformance.objects.get(user=self.user, topic="Biology")
        self.assertEqual(performance.total_questions, 4)
        self.assertEqual(performance.correct_answers, 3)
        self.assertEqual(performance.accuracy, 75.0)

        async_to_sync(update_topic_performance)(self.user, "Biology", 1, 2)
        performance.refresh_from_db()
        self.assertEqual(performance.total_questions, 6)
        self.assertEqual(performance.correct_answers, 4)
        self.assertEqual(performance.accuracy, 66.67)


class UpdateQuizScheduleTests(TestCase):
    def setUp(self):
        from apps.accounts.models import User

        self.user = User.objects.create_user(
            email="schedule@example.com", username="schedule"
        )

    def test_creates_schedule_and_applies_sm2(self):
        from asgiref.sync import async_to_sync

        from apps.quiz.models import QuizTopicSchedule
        from apps.quiz.utils.scheduling import update_quiz_schedule

        async_to_sync(update_quiz_schedule)(self.user, "Biology", 95)

        schedule = QuizTopicSchedule.objects.get(user=self.user, topic="Biology")
        self.assertEqual(schedule.repetition, 1)
        self.assertEqual(schedule.interval, 1)
        self.assertIsNotNone(schedule.last_review)
        self.assertGreater(schedule.next_review, schedule.last_review)

    def test_low_score_resets_repetition(self):
        from asgiref.sync import async_to_sync

        from apps.quiz.models import QuizTopicSchedule
        from apps.quiz.utils.scheduling import update_quiz_schedule

        schedule = QuizTopicSchedule.objects.create(
            user=self.user,
            topic="Biology",
            subject="Biology",
            repetition=3,
            interval=10,
        )

        async_to_sync(update_quiz_schedule)(self.user, "Biology", 10)

        schedule.refresh_from_db()
        self.assertEqual(schedule.repetition, 0)
        self.assertEqual(schedule.interval, 1)