from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.tutor.views import TutorChatStreamView, TutorChatView


class TutorAPIViewTests(SimpleTestCase):
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
        respond_turn.assert_awaited_once()

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

        stream_turn.side_effect = events
        request = self.factory.post(
            "/api/tutor/chat/stream/", {"message": "Hi"}, format="json"
        )

        response = TutorChatStreamView.as_view()(request)
        body = b"".join(async_to_sync(_collect)(response.streaming_content))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        self.assertIn(b'data: {"type": "token", "content": "Hello"}', body)


async def _collect(content):
    return b"".join([chunk async for chunk in content])
