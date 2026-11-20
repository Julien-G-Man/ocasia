"""Flashcard-domain generation backed by Django's in-process AI engine."""

import json
import logging
import re

from apps.core.ai_engine import ai_client
from apps.core.ai_engine.utils import _coerce_text, _extract_json_substring
from apps.flashcards.prompts import build_flashcards_prompt, build_flashcards_repair_prompt

logger = logging.getLogger(__name__)
_CARD_WRAPPER_KEYS = ("cards", "flashcards", "items", "data", "results", "questions")


class FlashcardGenerationError(ValueError):
    """The provider responded, but its flashcards could not be validated."""


def _parse_response(raw):
    if isinstance(raw, (list, dict)):
        return raw
    text = _coerce_text(raw)
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return _extract_json_substring(text)


def _normalize_cards(raw, limit: int) -> list[dict]:
    if isinstance(raw, dict):
        wrapped = next((raw[key] for key in _CARD_WRAPPER_KEYS if isinstance(raw.get(key), list)), None)
        if wrapped is None:
            wrapped = next((value for value in raw.values() if isinstance(value, list)), [])
        raw = wrapped
    if not isinstance(raw, list):
        return []

    cards, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or item.get("front") or "").strip()[:2000]
        answer = str(item.get("answer") or item.get("back") or "").strip()[:4000]
        key = (" ".join(question.casefold().split()), " ".join(answer.casefold().split()))
        if question and answer and key not in seen:
            seen.add(key)
            cards.append({"question": question, "answer": answer})
        if len(cards) >= limit:
            break
    return cards


async def generate_flashcards(
    *, text: str, subject: str, num_cards: int = 10,
    difficulty: str = "intermediate", prompt: str = "",
) -> dict:
    """Generate cards with AI Engine provider fallback and validate service output."""
    subject = subject.strip() if isinstance(subject, str) else ""
    text = text.strip() if isinstance(text, str) else ""
    prompt = prompt.strip() if isinstance(prompt, str) else ""
    if not subject:
        raise ValueError("Subject is required.")
    if len(text) < 30:
        raise ValueError("Study text must contain at least 30 characters.")
    if len(text) > 50_000:
        text = text[:50_000]
    try:
        num_cards = max(1, min(int(num_cards), 25))
    except (TypeError, ValueError) as exc:
        raise ValueError("Number of cards must be an integer.") from exc
    difficulty = str(difficulty or "").lower()
    difficulty = difficulty if difficulty in {"beginner", "intermediate", "exam"} else "intermediate"

    raw = await ai_client.generate_text(
        build_flashcards_prompt(
            subject=subject, text=text[:16_000], num_cards=num_cards,
            difficulty=difficulty, additional_instructions=prompt[:1500],
        ),
        max_tokens=1200,
        timeout=30,
    )
    cards = _normalize_cards(_parse_response(raw), num_cards)
    if not cards:
        logger.warning("Flashcard provider returned invalid output; attempting one repair.")
        repaired = await ai_client.generate_text(
            build_flashcards_repair_prompt(_coerce_text(raw)[:6000]),
            max_tokens=1200,
            timeout=30,
        )
        cards = _normalize_cards(_parse_response(repaired), num_cards)
    if not cards:
        raise FlashcardGenerationError("AI returned an invalid flashcards format.")
    return {"cards": cards, "fallback_used": False}
