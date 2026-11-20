from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.tutor.models import TutorMessage, TutorSession
from apps.tutor.views import (
    TutorChatStreamView,
    TutorChatView,
    TutorDocumentUploadView,
    TutorSessionDetailView,
    TutorSessionListView,
)


class TutorAPIViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("apps.tutor.views.TutorChatService.respond_turn", new_callable=AsyncMock)
    def test_chat_returns_agent_result(self, respond_turn):
        respond_turn.return_value = SimpleNamespace(
            response="Hello", tool_calls_made=[], action=None, prefill=None
        )
        request = self.factory.post(
            "/api/tutor/chat/", {"message": "Hi"}, format="json"
        )

        response = TutorChatView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["response"], "Hello")
        session = TutorSession.objects.get(session_id=response.data["session_id"])
        self.assertEqual(session.title, "Hi")
        self.assertEqual(
            list(session.messages.values_list("sender", "content")),
            [("user", "Hi"), ("ai", "Hello")],
        )
        respond_turn.assert_awaited_once()

    @patch("apps.tutor.views.TutorChatService.respond_turn", new_callable=AsyncMock)
    def test_chat_uses_saved_messages_as_follow_up_history(self, respond_turn):
        respond_turn.return_value = SimpleNamespace(
            response="The answer", tool_calls_made=[], action=None, prefill=None
        )
        session = TutorSession.objects.create(session_id="existing-session")
        TutorMessage.objects.create(session=session, sender="user", content="First question")
        TutorMessage.objects.create(session=session, sender="ai", content="First answer")
        request = self.factory.post(
            "/api/tutor/chat/",
            {"message": "Follow up", "session_id": session.session_id},
            format="json",
        )

        response = TutorChatView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        history = respond_turn.await_args.kwargs["history"]
        self.assertEqual(history, [
            {"role": "user", "content": "First question"},
            {"role": "ai", "content": "First answer"},
        ])
        self.assertEqual(session.messages.count(), 4)

    @patch("apps.tutor.views.TutorChatService.respond_turn", new_callable=AsyncMock)
    def test_chat_does_not_allow_access_to_another_users_session(self, respond_turn):
        owner = User.objects.create_user(email="owner@example.com", username="owner")
        other_user = User.objects.create_user(email="other@example.com", username="other")
        session = TutorSession.objects.create(
            session_id="private-session", user=owner
        )
        request = self.factory.post(
            "/api/tutor/chat/",
            {"message": "Try to read history", "session_id": session.session_id},
            format="json",
        )
        force_authenticate(request, user=other_user)

        response = TutorChatView.as_view()(request)

        self.assertEqual(response.status_code, 404)
        respond_turn.assert_not_awaited()

    @patch("apps.tutor.views.TutorChatService.respond_turn", new_callable=AsyncMock)
    def test_chat_rejects_invalid_payload(self, respond_turn):
        request = self.factory.post("/api/tutor/chat/", {"message": " "}, format="json")

        response = TutorChatView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        respond_turn.assert_not_awaited()

    @patch("apps.tutor.views.TutorChatService.stream_turn")
    def test_stream_returns_server_sent_events(self, stream_turn):
        async def events(**_kwargs):
            yield {"type": "token", "content": "Hello"}
            yield {"type": "done", "side_data": {}}

        stream_turn.side_effect = events
        request = self.factory.post(
            "/api/tutor/chat/stream/", {"message": "Hi"}, format="json"
        )

        response = TutorChatStreamView.as_view()(request)
        body = async_to_sync(_collect)(response.streaming_content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        self.assertTrue(response["X-Tutor-Session-ID"])
        self.assertIn(b'data: {"type": "token", "content": "Hello"}', body)
        session = TutorSession.objects.get(session_id=response["X-Tutor-Session-ID"])
        self.assertEqual(
            list(session.messages.values_list("sender", "content")),
            [("user", "Hi"), ("ai", "Hello")],
        )


async def _collect(content):
    return b"".join([chunk async for chunk in content])


class TutorSessionManagementApiTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(email="owner@example.com", username="owner")
        self.session = TutorSession.objects.create(
            session_id="session-1", user=self.user, title="Photosynthesis"
        )
        TutorMessage.objects.create(session=self.session, sender="user", content="What is photosynthesis?")
        TutorMessage.objects.create(session=self.session, sender="ai", content="It is a process.")

    def test_list_returns_only_own_sessions(self):
        other = User.objects.create_user(email="other@example.com", username="other")
        TutorSession.objects.create(session_id="session-2", user=other)

        request = self.factory.get("/api/tutor/sessions/")
        force_authenticate(request, user=self.user)

        response = TutorSessionListView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        history = response.data["history"]
        self.assertEqual([item["session_id"] for item in history], ["session-1"])
        self.assertEqual(history[0]["message_count"], 2)
        self.assertEqual(history[0]["last_message"], "It is a process.")

    def test_list_requires_authentication(self):
        request = self.factory.get("/api/tutor/sessions/")

        response = TutorSessionListView.as_view()(request)

        self.assertEqual(response.status_code, 401)

    def test_detail_returns_ordered_messages(self):
        request = self.factory.get(f"/api/tutor/sessions/{self.session.session_id}/")
        force_authenticate(request, user=self.user)

        response = TutorSessionDetailView.as_view()(request, session_id=self.session.session_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message_count"], 2)
        self.assertEqual(
            [message["sender"] for message in response.data["messages"]],
            ["user", "ai"],
        )

    def test_detail_hides_other_users_session(self):
        request = self.factory.get(f"/api/tutor/sessions/{self.session.session_id}/")
        force_authenticate(request, user=User.objects.create_user(email="x@example.com", username="x"))

        response = TutorSessionDetailView.as_view()(request, session_id=self.session.session_id)

        self.assertEqual(response.status_code, 404)

    def test_rename_updates_title(self):
        request = self.factory.patch(
            f"/api/tutor/sessions/{self.session.session_id}/",
            {"title": "Renamed"},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = TutorSessionDetailView.as_view()(request, session_id=self.session.session_id)

        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.title, "Renamed")

    def test_delete_removes_session_and_messages(self):
        request = self.factory.delete(f"/api/tutor/sessions/{self.session.session_id}/")
        force_authenticate(request, user=self.user)

        response = TutorSessionDetailView.as_view()(request, session_id=self.session.session_id)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TutorSession.objects.filter(session_id="session-1").exists())
        self.assertFalse(TutorMessage.objects.filter(session=self.session).exists())


class TutorDocumentUploadApiTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(email="uploader@example.com", username="uploader")

    def _upload(self, *, name="notes.txt", content=b"Photosynthesis converts light into energy."):
        upload = SimpleUploadedFile(name, content, content_type="text/plain")
        return self.factory.post(
            "/api/tutor/upload/",
            {"file_upload": upload, "message": "Summarize this"},
            format="multipart",
        )

    @patch("apps.tutor.views.TutorChatService.respond_turn", new_callable=AsyncMock)
    def test_upload_extracts_text_and_returns_response(self, respond_turn):
        respond_turn.return_value = SimpleNamespace(
            response="Here is the summary.", tool_calls_made=[], action=None, prefill=None
        )
        request = self._upload()
        force_authenticate(request, user=self.user)

        response = TutorDocumentUploadView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["response"], "Here is the summary.")
        self.assertEqual(response.data["filename"], "notes.txt")
        session = TutorSession.objects.get(session_id=response.data["session_id"])
        self.assertTrue(session.has_document)
        self.assertEqual(
            list(session.messages.values_list("sender", "content")),
            [("user", "Summarize this"), ("ai", "Here is the summary.")],
        )
        respond_turn.assert_awaited_once()
        self.assertIn("Photosynthesis", respond_turn.await_args.kwargs["file_text"])

    def test_upload_rejects_unsupported_file_type(self):
        request = self._upload(name="data.csv", content=b"a,b,c")
        force_authenticate(request, user=self.user)

        response = TutorDocumentUploadView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(TutorSession.objects.exists())
