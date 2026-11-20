from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.tutor.models import TutorMessage, TutorSession
from apps.tutor.views import TutorChatStreamView, TutorChatView


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
