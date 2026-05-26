import asyncio
import logging
from fastapi import APIRouter, HTTPException
from core.ai_client import ai_client, APIIntegrationError
from core.http import get_async_client
from core.config import settings
from .prompts import DIFFICULTY_PROMPTS, FORMATTING_GUIDELINES
from .schemas import FlashcardRequest, FlashcardExplainRequest
from .helpers import _normalize_cards


flashcards_router = APIRouter()
logger = logging.getLogger(__name__)

AI_MAX_CONCURRENT = max(20, settings.FLASHCARDS_AI_MAX_CONCURRENT)
AI_SEMAPHORE_WAIT_SECONDS = settings.FLASHCARDS_AI_SEMAPHORE_WAIT_SECONDS
_ai_semaphore = asyncio.Semaphore(AI_MAX_CONCURRENT)


async def _try_acquire_ai_slot() -> bool:
    try:
        await asyncio.wait_for(_ai_semaphore.acquire(), timeout=AI_SEMAPHORE_WAIT_SECONDS)
        return True
    except TimeoutError:
        return False


@flashcards_router.post("/generate")
async def generate_flashcards(data: FlashcardRequest):
    client = await get_async_client()

    subject = data.subject
    text = data.text
    num_cards = data.num_cards
    difficulty = data.difficulty
    user_prompt = data.prompt or ""

    difficulty_prompt = DIFFICULTY_PROMPTS.get(
        difficulty,
        DIFFICULTY_PROMPTS["intermediate"]
    )

    prompt = f"""
You are an expert study assistant.

Subject: {subject}

Content:
{text}

Additional instructions:
{user_prompt}

Difficulty level:
{difficulty_prompt}

{FORMATTING_GUIDELINES}

Create {num_cards} flashcards.

Return ONLY valid JSON in this format:

[
  {{
    "question": "...",
    "answer": "..."
  }}
]
"""

    if not await _try_acquire_ai_slot():
        logger.warning("Flashcards generation overload: rejecting request")
        raise HTTPException(
            status_code=503,
            detail="Flashcards service is under high load. Please try again shortly.",
        )

    try:
        result = await ai_client.generate_content(client=client, prompt=prompt, max_tokens=1200, timeout=30)

        cards = _normalize_cards(result)
        if cards:
            return {
                "cards": cards,
                "fallback_used": False,
            }

        raise HTTPException(
            status_code=502,
            detail="AI returned an invalid flashcards format.",
        )

    except APIIntegrationError as exc:
        logger.warning("Flashcards provider unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"AI provider unavailable: {str(exc)}",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected flashcards generation error: %s", exc)
        raise HTTPException(status_code=500, detail="Unexpected flashcards generation error.")
    finally:
        _ai_semaphore.release()


@flashcards_router.post("/explain")
async def explain_flashcard(data: FlashcardExplainRequest):
    client = await get_async_client()

    question = data.question
    answer = data.answer

    prompt = f"""
A student failed a flashcard.

Question:
{question}

Correct Answer:
{answer}

Explain this concept clearly in 3 short sentences
like a tutor helping a beginner.

{FORMATTING_GUIDELINES}
"""

    if not await _try_acquire_ai_slot():
        logger.warning("Flashcards explanation overload: rejecting request")
        raise HTTPException(
            status_code=503,
            detail="Flashcards explanation service is under high load. Please try again shortly.",
        )

    try:
        result = await ai_client.generate_content(client=client, prompt=prompt, max_tokens=200, timeout=30)

        if isinstance(result, str) and result.strip():
            return {
                "explanation": result.strip(),
                "fallback_used": False,
            }

        raise HTTPException(status_code=502, detail="AI returned an empty explanation.")

    except APIIntegrationError as exc:
        logger.warning("Flashcards explanation provider unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"AI provider unavailable: {str(exc)}",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected flashcards explanation error: %s", exc)
        raise HTTPException(status_code=500, detail="Unexpected flashcards explanation error.")
    finally:
        _ai_semaphore.release()
