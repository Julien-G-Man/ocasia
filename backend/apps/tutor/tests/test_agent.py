from unittest.mock import patch

from django.test import SimpleTestCase
from langchain_core.messages import AIMessage

from apps.tutor.agent.runner import TutorAgent


class _FakeModel:
    """Minimal stand-in for a tool-bound chat model."""

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        return AIMessage(content="A clear answer.")

    async def astream(self, messages):
        yield AIMessage(content="A clear answer.")


class TutorAgentTests(SimpleTestCase):
    async def test_run_rejects_empty_message_before_calling_model(self):
        agent = TutorAgent("   ")

        with self.assertRaisesMessage(ValueError, "message must not be empty"):
            await agent.run()

    async def test_stream_reports_empty_message(self):
        agent = TutorAgent("   ")

        events = [event async for event in agent.stream()]

        self.assertEqual(
            events, [{"type": "error", "message": "message must not be empty"}]
        )

    @patch("apps.tutor.agent.runner.build_chat_model", return_value=_FakeModel())
    async def test_run_returns_model_response(self, _build_model):
        agent = TutorAgent(
            "What is recursion?",
            history=[{"message_type": "user", "content": "I am learning algorithms."}],
        )

        result = await agent.run()

        self.assertEqual(result.response, "A clear answer.")
        self.assertEqual(result.tool_calls_made, [])

    @patch("apps.tutor.agent.runner.build_chat_model", return_value=_FakeModel())
    async def test_stream_emits_tokens_then_done(self, _build_model):
        agent = TutorAgent("What is recursion?")

        events = [event async for event in agent.stream()]

        self.assertEqual(events[0], {"type": "token", "content": "A clear answer."})
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(events[-1]["side_data"], {})