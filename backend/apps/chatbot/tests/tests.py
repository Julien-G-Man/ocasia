import httpx
from unittest.mock import AsyncMock, patch

from django.test import AsyncClient, TestCase
from rest_framework.authtoken.models import Token

from apps.accounts.models import User
from apps.chatbot.helpers import (
    _derive_session_title,
    chunk_text,
    fallback_response,
)
from apps.chatbot.models import ChatMessage, ChatSession


class ChatHelperTests(TestCase):
    def test_derive_session_title_uses_first_sentence_and_limit(self):
        self.assertEqual(
            _derive_session_title("Explain photosynthesis. Then give examples."),
            "Explain photosynthesis",
        )
        self.assertLessEqual(len(_derive_session_title("a" * 150)), 120)

    def test_chunk_text_overlaps_and_preserves_words(self):
        chunks = chunk_text(" ".join(f"word{i}" for i in range(12)), size=5, overlap=2)

        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0][-2:], ["word3", "word4"])
        self.assertEqual(chunks[1][:2], ["word3", "word4"])

    def test_chunk_text_rejects_empty_input(self):
        self.assertEqual(chunk_text("", size=5, overlap=1), [])

    def test_fallback_response_for_greeting(self):
        self.assertIn("Ocasia AI Tutor", fallback_response("hello"))


class ChatbotApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="junior@example.com",
            username="junior",
            password="test-password",
        )
        self.token = Token.objects.create(user=self.user)
        self.client = AsyncClient()
        self.headers = {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

    async def test_chat_requires_authentication(self):
        response = await self.client.post(
            "/api/chat/",
            data={"message": "Hello"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)

    async def test_chat_requires_message(self):
        response = await self.client.post(
            "/api/chat/",
            data={},
            content_type="application/json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 400)

    @patch(
        "apps.chatbot.async_views.call_fastapi",
        new=AsyncMock(
            return_value=httpx.Response(
                200,
                json={"response": "Mock AI response", "action": None, "prefill": None},
            )
        ),
    )
    async def test_chat_creates_session_and_persists_turn(self, _mock):
        response = await self.client.post(
            "/api/chat/",
            data={"message": "Explain fractions"},
            content_type="application/json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["response"], "Mock AI response")
        self.assertTrue(payload["session_id"])

        session = await ChatSession.objects.aget(session_id=payload["session_id"])
        messages = [message async for message in session.messages.order_by("created_at")]
        self.assertEqual([message.sender for message in messages], ["user", "ai"])
        self.assertEqual(messages[0].content, "Explain fractions")
        self.assertEqual(messages[1].content, "Mock AI response")

    async def test_user_cannot_use_another_users_session(self):
        other = await User.objects.acreate(
            email="other@example.com",
            username="other",
            is_active=True,
        )
        other_session = await ChatSession.objects.acreate(
            user=other,
            session_id="private-session",
        )

        response = await self.client.post(
            "/api/chat/",
            data={"message": "Read this", "session_id": "private-session"},
            content_type="application/json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 401)
        await other_session.arefresh_from_db()
        self.assertEqual(other_session.user_id, other.id)
        self.assertFalse(
            await ChatSession.objects.filter(
                session_id="private-session",
                user=self.user,
            ).aexists()
        )
