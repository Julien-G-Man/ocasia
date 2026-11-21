from datetime import timedelta
from unittest.mock import AsyncMock, patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.core.ai_engine import APIIntegrationError
from apps.quiz.models import QuizSession, QuizTopicSchedule, TopicPerformance
from apps.quiz.utils.download_helpers import HAS_REPORTLAB
from apps.quiz.views import (
    DueTopicsView,
    QuizDownloadView,
    QuizExtractTextView,
    QuizGenerateView,
    QuizHistoryView,
    QuizReplayView,
    QuizSubmitView,
    QuizYouTubeExtractView,
    WeakAreasView,
)

STUDY_TEXT = "Photosynthesis converts light energy into chemical energy in plants."


class QuizGenerateViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            email="generate@example.com", username="generate"
        )

    def _post(self, payload):
        request = self.factory.post("/api/quiz/generate/", payload, format="json")
        force_authenticate(request, user=self.user)
        return QuizGenerateView.as_view()(request)

    @patch("apps.quiz.views.generate_quiz", new_callable=AsyncMock)
    def test_returns_quiz_with_metadata(self, generate_quiz):
        generate_quiz.return_value = {
            "subject": "Biology",
            "study_text": STUDY_TEXT,
            "difficulty": "medium",
            "mcq_questions": [],
            "short_questions": [],
        }

        response = self._post(
            {
                "subject": "Biology",
                "extractedText": STUDY_TEXT,
                "num_mcq": 1,
                "num_short": 0,
                "difficulty": "random",
                "source_filename": "notes.pdf",
                "quiz_time": 15,
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["id"])
        self.assertEqual(response.data["time_limit"], 15)
        self.assertIsNone(response.data["created_at"])
        self.assertEqual(response.data["source_filename"], "notes.pdf")

        generate_quiz.assert_awaited_once()
        kwargs = generate_quiz.await_args.kwargs
        self.assertEqual(kwargs["subject"], "Biology")
        self.assertEqual(kwargs["study_text"], STUDY_TEXT)
        self.assertEqual(kwargs["num_mcq"], 1)
        self.assertEqual(kwargs["num_short"], 0)
        self.assertEqual(kwargs["difficulty"], "random")
        self.assertEqual(kwargs["source_type"], "text")
        self.assertEqual(kwargs["source_title"], "notes.pdf")

    def test_rejects_short_study_text(self):
        response = self._post({"subject": "Biology", "extractedText": "short"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("30 characters", response.data["error"])

    def test_requires_authentication(self):
        request = self.factory.post(
            "/api/quiz/generate/", {"extractedText": STUDY_TEXT}, format="json"
        )

        response = QuizGenerateView.as_view()(request)

        self.assertEqual(response.status_code, 401)

    @patch("apps.quiz.views.generate_quiz", new_callable=AsyncMock)
    def test_value_error_returns_400(self, generate_quiz):
        generate_quiz.side_effect = ValueError("Subject is required.")

        response = self._post({"subject": "Biology", "extractedText": STUDY_TEXT})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "Subject is required.")

    @patch("apps.quiz.views.generate_quiz", new_callable=AsyncMock)
    def test_provider_error_returns_503(self, generate_quiz):
        generate_quiz.side_effect = APIIntegrationError("provider down")

        response = self._post({"subject": "Biology", "extractedText": STUDY_TEXT})

        self.assertEqual(response.status_code, 503)
        self.assertIn("unavailable", response.data["error"])

    @patch("apps.quiz.views.generate_quiz", new_callable=AsyncMock)
    def test_zero_mcq_is_allowed(self, generate_quiz):
        generate_quiz.return_value = {"mcq_questions": [], "short_questions": []}

        response = self._post(
            {
                "subject": "Biology",
                "extractedText": STUDY_TEXT,
                "num_mcq": 0,
                "num_short": 2,
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate_quiz.await_args.kwargs["num_mcq"], 0)


class QuizSubmitViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            email="submit@example.com", username="submit"
        )

    def _post(self, payload):
        request = self.factory.post("/api/quiz/submit/", payload, format="json")
        force_authenticate(request, user=self.user)
        return QuizSubmitView.as_view()(request)

    @patch("apps.quiz.views.submit_quiz", new_callable=AsyncMock)
    def test_returns_results_and_forwards_options(self, submit_quiz):
        submit_quiz.return_value = {"score": 1, "total": 1, "score_percent": 100.0}

        response = self._post(
            {
                "quiz_data": {"mcq_questions": []},
                "user_answers": {"0": "A"},
                "quiz_id": "qid",
                "duration_minutes": 3,
                "time_limit": 10,
                "exam_mode": True,
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["score"], 1)

        kwargs = submit_quiz.await_args.kwargs
        self.assertEqual(kwargs["user"], self.user)
        self.assertEqual(kwargs["quiz_data"], {"mcq_questions": []})
        self.assertEqual(kwargs["user_answers"], {"0": "A"})
        self.assertEqual(kwargs["quiz_id"], "qid")
        self.assertEqual(kwargs["duration_minutes"], 3)
        self.assertEqual(kwargs["time_limit"], 10)
        self.assertTrue(kwargs["exam_mode"])

    def test_missing_quiz_data_returns_400(self):
        response = self._post({})

        self.assertEqual(response.status_code, 400)
        self.assertIn("quiz_data", response.data)

    @patch("apps.quiz.views.submit_quiz", new_callable=AsyncMock)
    def test_value_error_returns_400(self, submit_quiz):
        submit_quiz.side_effect = ValueError("No questions found in quiz data")

        response = self._post({"quiz_data": {"mcq_questions": []}})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "No questions found in quiz data")

    def test_requires_authentication(self):
        request = self.factory.post(
            "/api/quiz/submit/", {"quiz_data": {"mcq_questions": []}}, format="json"
        )

        response = QuizSubmitView.as_view()(request)

        self.assertEqual(response.status_code, 401)


class QuizExtractTextViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            email="extract@example.com", username="extract"
        )

    def _post(self, upload=None):
        data = {"slide_file": upload} if upload else {}
        request = self.factory.post(
            "/api/quiz/extract-text/", data, format="multipart"
        )
        force_authenticate(request, user=self.user)
        return QuizExtractTextView.as_view()(request)

    def test_extracts_text_from_txt(self):
        upload = SimpleUploadedFile(
            "notes.txt",
            b"Photosynthesis converts light.",
            content_type="text/plain",
        )

        response = self._post(upload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["text"], "Photosynthesis converts light.")

    def test_missing_file_returns_400(self):
        response = self._post()

        self.assertEqual(response.status_code, 400)
        self.assertIn("No file uploaded", response.data["error"])

    def test_unsupported_file_returns_400(self):
        upload = SimpleUploadedFile(
            "data.csv", b"a,b,c", content_type="text/csv"
        )

        response = self._post(upload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported file format", response.data["error"])

    @patch("apps.quiz.views.MAX_UPLOAD_BYTES", 5)
    def test_oversized_file_returns_400(self):
        upload = SimpleUploadedFile(
            "notes.txt", b"123456789", content_type="text/plain"
        )

        response = self._post(upload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("too large", response.data["error"])

    @patch("apps.quiz.views.MAX_STUDY_TEXT", 10)
    def test_truncates_long_text(self):
        upload = SimpleUploadedFile(
            "notes.txt", b"x" * 100, content_type="text/plain"
        )

        response = self._post(upload)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["text"].endswith("... [truncated]"))
        self.assertEqual(
            len(response.data["text"]), len("x" * 10 + "... [truncated]")
        )

    def test_requires_authentication(self):
        upload = SimpleUploadedFile(
            "notes.txt", b"hello", content_type="text/plain"
        )
        request = self.factory.post(
            "/api/quiz/extract-text/", {"slide_file": upload}, format="multipart"
        )

        response = QuizExtractTextView.as_view()(request)

        self.assertEqual(response.status_code, 401)


class QuizYouTubeExtractViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            email="youtube@example.com", username="youtube"
        )

    def _post(self, payload):
        request = self.factory.post("/api/quiz/extract-youtube/", payload, format="json")
        force_authenticate(request, user=self.user)
        return QuizYouTubeExtractView.as_view()(request)

    @patch("apps.quiz.views.fetch_youtube_quiz_content", new_callable=AsyncMock)
    def test_returns_transcript_payload(self, fetch_content):
        fetch_content.return_value = {
            "text": "transcript",
            "title": "Video",
            "video_id": "dQw4w9WgXcQ",
        }

        response = self._post({"url": "https://youtu.be/dQw4w9WgXcQ"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["video_id"], "dQw4w9WgXcQ")
        fetch_content.assert_awaited_once_with("https://youtu.be/dQw4w9WgXcQ")

    def test_invalid_url_returns_400(self):
        response = self._post({"url": "not-a-url"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("url", response.data)

    @patch("apps.quiz.views.fetch_youtube_quiz_content", new_callable=AsyncMock)
    def test_value_error_returns_400(self, fetch_content):
        fetch_content.side_effect = ValueError("Captions are disabled.")

        response = self._post({"url": "https://youtu.be/dQw4w9WgXcQ"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "Captions are disabled.")

    def test_requires_authentication(self):
        request = self.factory.post(
            "/api/quiz/extract-youtube/",
            {"url": "https://youtu.be/dQw4w9WgXcQ"},
            format="json",
        )

        response = QuizYouTubeExtractView.as_view()(request)

        self.assertEqual(response.status_code, 401)


class QuizDownloadViewTests(TestCase):
    RESULTS = {
        "subject": "Biology",
        "difficulty": "medium",
        "details": [
            {
                "question": "What absorbs light?",
                "options": ["Chlorophyll", "Water"],
                "correct_answer": "A",
                "explanation": "Chlorophyll absorbs light.",
            }
        ],
    }

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            email="download@example.com", username="download"
        )

    def _post(self, payload):
        request = self.factory.post("/api/quiz/download/", payload, format="json")
        force_authenticate(request, user=self.user)
        return QuizDownloadView.as_view()(request)

    def test_returns_txt_attachment(self):
        response = self._post({"results": self.RESULTS, "format": "txt"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(b"BIOLOGY", response.content)

    def test_defaults_to_pdf(self):
        if not HAS_REPORTLAB:
            self.skipTest("reportlab is not installed")

        response = self._post({"results": self.RESULTS})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_missing_results_returns_400(self):
        response = self._post({})

        self.assertEqual(response.status_code, 400)
        self.assertIn("No results data provided", response.data["error"])

    def test_requires_authentication(self):
        request = self.factory.post(
            "/api/quiz/download/", {"results": self.RESULTS}, format="json"
        )

        response = QuizDownloadView.as_view()(request)

        self.assertEqual(response.status_code, 401)


class QuizHistoryViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            email="history@example.com", username="history"
        )

    def test_returns_own_history(self):
        QuizSession.objects.create(
            user=self.user,
            subject="Biology",
            total_questions=2,
            correct_answers=1,
            score_percentage=50,
        )

        request = self.factory.get("/api/quiz/history/")
        force_authenticate(request, user=self.user)
        response = QuizHistoryView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["history"][0]["subject"], "Biology")
        self.assertEqual(response.data["history"][0]["score_percent"], 50.0)

    def test_requires_authentication(self):
        request = self.factory.get("/api/quiz/history/")

        response = QuizHistoryView.as_view()(request)

        self.assertEqual(response.status_code, 401)


class QuizReplayViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            email="replay@example.com", username="replay"
        )
        self.other = User.objects.create_user(
            email="other@example.com", username="other"
        )

    def test_returns_stored_data(self):
        session = QuizSession.objects.create(
            user=self.user, questions_data={"mcq_questions": []}
        )

        request = self.factory.get(f"/api/quiz/sessions/{session.id}/")
        force_authenticate(request, user=self.user)
        response = QuizReplayView.as_view()(request, session_id=session.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["quiz_data"], {"mcq_questions": []})

    def test_hides_other_users_session(self):
        session = QuizSession.objects.create(user=self.other, questions_data={})

        request = self.factory.get(f"/api/quiz/sessions/{session.id}/")
        force_authenticate(request, user=self.user)
        response = QuizReplayView.as_view()(request, session_id=session.id)

        self.assertEqual(response.status_code, 404)

    def test_requires_authentication(self):
        session = QuizSession.objects.create(user=self.user, questions_data={})

        request = self.factory.get(f"/api/quiz/sessions/{session.id}/")
        response = QuizReplayView.as_view()(request, session_id=session.id)

        self.assertEqual(response.status_code, 401)


class WeakAreasViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            email="weak@example.com", username="weak"
        )

    def test_returns_weak_areas(self):
        TopicPerformance.objects.create(
            user=self.user,
            topic="Weak",
            subject="Weak",
            total_questions=5,
            correct_answers=1,
            accuracy=20,
        )

        request = self.factory.get("/api/quiz/weak-areas/")
        force_authenticate(request, user=self.user)
        response = WeakAreasView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["weak_areas"][0]["topic"], "Weak")

    def test_requires_authentication(self):
        request = self.factory.get("/api/quiz/weak-areas/")

        response = WeakAreasView.as_view()(request)

        self.assertEqual(response.status_code, 401)


class DueTopicsViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            email="due@example.com", username="due"
        )

    def test_returns_due_topics(self):
        QuizTopicSchedule.objects.create(
            user=self.user,
            topic="Overdue",
            subject="Overdue",
            next_review=timezone.now() - timedelta(days=1),
        )

        request = self.factory.get("/api/quiz/due-topics/")
        force_authenticate(request, user=self.user)
        response = DueTopicsView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["due_topics"][0]["topic"], "Overdue")

    def test_requires_authentication(self):
        request = self.factory.get("/api/quiz/due-topics/")

        response = DueTopicsView.as_view()(request)

        self.assertEqual(response.status_code, 401)