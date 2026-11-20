import json
from unittest.mock import AsyncMock, patch

from django.test import SimpleTestCase

from apps.flashcards.services import generate_flashcards
from apps.quiz.services import QuizGenerationError, generate_quiz
from apps.tutor.agent.tools.content import (
    generate_flashcards as agent_generate_flashcards,
    generate_quiz as agent_generate_quiz,
)


STUDY_TEXT = "Photosynthesis converts light energy into chemical energy in plants. Chlorophyll absorbs light."


class QuizServiceTests(SimpleTestCase):
    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_generates_and_normalizes_quiz_questions_via_ai_engine(self, generate_text):
        generate_text.return_value = json.dumps({
            "mcq_questions": [{
                "question": "What does photosynthesis convert?",
                "options": ["Light energy", "Water", "Oxygen", "Heat"],
                "answer": "a",
                "explanation": "Plants convert light energy into stored chemical energy.",
            }],
            "short_questions": [{"question": "What absorbs light?", "answer": "Chlorophyll"}],
        })

        result = await generate_quiz(
            subject="Biology", study_text=STUDY_TEXT, num_mcq=1, num_short=1,
            source_type="file", source_title="notes.pdf",
        )

        self.assertEqual(result["mcq_questions"][0]["answer"], "A")
        self.assertEqual(result["short_questions"][0]["type"], "short")
        self.assertEqual(result["study_text"], STUDY_TEXT)
        self.assertIn("OCR/PDF artifacts", generate_text.await_args.args[0])
        self.assertEqual(generate_text.await_args.kwargs["timeout"], 60)

    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_repairs_malformed_quiz_json_once(self, generate_text):
        generate_text.side_effect = ["not json", json.dumps({
            "mcq_questions": [{"question": "Q?", "options": ["a", "b", "c", "d"], "answer": "B"}],
            "short_questions": [],
        })]

        result = await generate_quiz(subject="Biology", study_text=STUDY_TEXT, num_mcq=1, num_short=0)

        self.assertEqual(len(result["mcq_questions"]), 1)
        self.assertEqual(generate_text.await_count, 2)

    @patch("apps.quiz.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_rejects_invalid_question_output(self, generate_text):
        generate_text.return_value = json.dumps({"mcq_questions": [], "short_questions": []})
        with self.assertRaises(QuizGenerationError):
            await generate_quiz(subject="Biology", study_text=STUDY_TEXT, num_mcq=1, num_short=0)


class FlashcardServiceTests(SimpleTestCase):
    @patch("apps.flashcards.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_normalizes_wrapped_cards_and_removes_duplicates(self, generate_text):
        generate_text.return_value = json.dumps({"data": [
            {"front": "What absorbs light?", "back": "Chlorophyll"},
            {"question": " What absorbs light? ", "answer": "Chlorophyll"},
        ]})

        result = await generate_flashcards(
            text=STUDY_TEXT, subject="Biology", num_cards=2, difficulty="exam"
        )

        self.assertEqual(result["cards"], [{"question": "What absorbs light?", "answer": "Chlorophyll"}])
        self.assertIn("university exam level", generate_text.await_args.args[0])

    @patch("apps.flashcards.services.ai_client.generate_text", new_callable=AsyncMock)
    async def test_repairs_invalid_flashcard_json(self, generate_text):
        generate_text.side_effect = ["bad", json.dumps([{"question": "Q", "answer": "A"}])]
        result = await generate_flashcards(text=STUDY_TEXT, subject="Biology")
        self.assertEqual(result["cards"], [{"question": "Q", "answer": "A"}])
        self.assertEqual(generate_text.await_count, 2)

    async def test_rejects_short_study_text_before_provider_call(self):
        with self.assertRaisesMessage(ValueError, "at least 30 characters"):
            await generate_flashcards(text="too short", subject="Biology")


class AgentStudyContentAdapterTests(SimpleTestCase):
    @patch("apps.tutor.agent.tools.content._retrieved_study_text", new_callable=AsyncMock)
    @patch("apps.quiz.services.generate_quiz", new_callable=AsyncMock)
    async def test_quiz_uses_chat_context_without_rag(self, quiz_service, retrieve):
        quiz_service.return_value = {"mcq_questions": []}
        result = await agent_generate_quiz(
            subject="Biology", study_text=STUDY_TEXT, source_type="file", source_title="notes.pdf"
        )
        self.assertEqual(result, {"mcq_questions": []})
        retrieve.assert_not_awaited()
        self.assertEqual(quiz_service.await_args.kwargs["study_text"], STUDY_TEXT)

    @patch("apps.tutor.agent.tools.content._retrieved_study_text", new_callable=AsyncMock)
    @patch("apps.quiz.services.generate_quiz", new_callable=AsyncMock)
    async def test_quiz_uses_rag_context_when_chat_has_no_material(self, quiz_service, retrieve):
        retrieve.return_value = "[Source: biology.pdf, page: 2]\n" + STUDY_TEXT
        quiz_service.return_value = {"mcq_questions": []}
        await agent_generate_quiz(subject="photosynthesis", num_mcq=1, num_short=0)
        retrieve.assert_awaited_once_with("photosynthesis")
        self.assertEqual(quiz_service.await_args.kwargs["source_type"], "retrieval")

    @patch("apps.tutor.agent.tools.content._retrieved_study_text", new_callable=AsyncMock)
    @patch("apps.flashcards.services.generate_flashcards", new_callable=AsyncMock)
    async def test_flashcards_resolve_topic_from_rag_before_generation(self, service, retrieve):
        retrieve.return_value = STUDY_TEXT
        service.return_value = {"cards": []}
        await agent_generate_flashcards(subject="photosynthesis")
        retrieve.assert_awaited_once_with("photosynthesis")
        self.assertEqual(service.await_args.kwargs["text"], STUDY_TEXT)
