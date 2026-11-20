from unittest.mock import AsyncMock, patch

from django.test import SimpleTestCase

from apps.tutor.chat_service import TutorChatService


class TutorChatServiceTests(SimpleTestCase):
    async def test_rejects_empty_messages_before_calling_agent(self):
        with self.assertRaisesMessage(ValueError, "message must not be empty"):
            await TutorChatService().respond("  ")

    @patch("apps.tutor.chat_service.run_tutor_agent", new_callable=AsyncMock)
    async def test_returns_agent_response(self, run_agent):
        run_agent.return_value.response = "A clear answer."

        response = await TutorChatService().respond(
            "What is recursion?",
            history=[{"message_type": "user", "content": "I am learning algorithms."}],
        )

        self.assertEqual(response, "A clear answer.")
        run_agent.assert_awaited_once()

