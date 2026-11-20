"""Quiz-domain generation service backed by Django's in-process AI engine."""

import json
import logging
import re
import unicodedata

from apps.core.ai_engine import ai_client
from apps.core.ai_engine.utils import _coerce_text, _extract_json_substring
from apps.quiz.prompts import build_quiz_prompt, build_repair_prompt

logger = logging.getLogger(__name__)
MAX_STUDY_CHARS = 16_000


class QuizGenerationError(ValueError):
    """The provider responded, but its quiz could not be validated."""


def normalize_study_text(text: str, max_chars: int = MAX_STUDY_CHARS) -> str:
    if not isinstance(text, str):
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    for old, new in {
        "\u00ad": "", "\ufeff": "", "\u200b": "", "\u2011": "-",
        "\u2013": "-", "\u2014": "-", "\ufb01": "fi", "\ufb02": "fl",
        "\u2212": "-", "\u00d7": " x ", "\u00f7": " / ",
    }.items():
        normalized = normalized.replace(old, new)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    return normalized[:max_chars]


def _parse_response(raw):
    if isinstance(raw, (dict, list)):
        return raw
    text = _coerce_text(raw)
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        parsed = _extract_json_substring(text)
        if isinstance(parsed, (dict, list)):
            return parsed
    return None


def _normalize_questions(data: dict, *, subject: str, difficulty: str, study_text: str,
                         num_mcq: int, num_short: int) -> dict:
    mcq_source = data.get("mcq_questions", [])
    short_source = data.get("short_questions", [])
    if not isinstance(mcq_source, list) or not isinstance(short_source, list):
        raise QuizGenerationError("AI returned an invalid quiz structure.")

    mcq = []
    for item in mcq_source:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        options = item.get("options")
        answer = str(item.get("answer") or "").strip().upper()
        if (
            question and isinstance(options, list) and len(options) == 4
            and all(str(option).strip() for option in options)
            and answer in {"A", "B", "C", "D"}
        ):
            mcq.append({
                "question": question,
                "type": "mcq",
                "options": [str(option).strip() for option in options],
                "answer": answer,
                "explanation": str(item.get("explanation") or "").strip(),
            })

    short = []
    for item in short_source:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        if question and answer:
            short.append({
                "question": question,
                "type": "short",
                "options": [],
                "answer": answer,
                "explanation": str(item.get("explanation") or "").strip(),
            })

    mcq, short = mcq[:num_mcq], short[:num_short]
    if len(mcq) < num_mcq or len(short) < num_short:
        logger.warning("Quiz provider returned fewer valid questions than requested (mcq=%d/%d short=%d/%d).",
                       len(mcq), num_mcq, len(short), num_short)
    if not mcq and not short:
        raise QuizGenerationError("AI returned no valid quiz questions.")
    return {
        "subject": subject,
        "study_text": study_text,
        "difficulty": difficulty,
        "mcq_questions": mcq,
        "short_questions": short,
    }


async def generate_quiz(
    *, subject: str, study_text: str, difficulty: str = "medium",
    num_mcq: int = 7, num_short: int = 3, source_type: str = "text",
    source_title: str = "",
) -> dict:
    """Generate and validate quiz data; raises ``APIIntegrationError`` on provider failure."""
    subject = subject.strip() if isinstance(subject, str) else ""
    study_text = normalize_study_text(study_text)
    if not subject:
        raise ValueError("Subject is required.")
    if len(study_text) < 30:
        raise ValueError("Study text must contain at least 30 characters.")
    try:
        num_mcq = max(0, min(int(num_mcq), 30))
        num_short = max(0, min(int(num_short), 10))
    except (TypeError, ValueError) as exc:
        raise ValueError("Question counts must be integers.") from exc
    if num_mcq + num_short == 0:
        raise ValueError("Request at least one quiz question.")
    difficulty = str(difficulty or "medium").lower()
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"
    source_type = str(source_type or "text").lower()
    source_type = source_type if source_type in {"text", "file", "youtube", "retrieval"} else "text"
    source_title = str(source_title or "")

    prompt = build_quiz_prompt(
        subject=subject, study_text=study_text, difficulty=difficulty,
        num_mcq=num_mcq, num_short=num_short, source_type=source_type,
        source_title=source_title or "",
    )
    token_budget = max(4096, min(8192, num_mcq * 250 + num_short * 150 + 1024))
    raw = await ai_client.generate_text(prompt, max_tokens=token_budget, timeout=60)
    data = _parse_response(raw)
    if isinstance(data, list):
        data = {"mcq_questions": data, "short_questions": []}
    if not isinstance(data, dict):
        logger.warning("Quiz provider returned malformed JSON; attempting one repair.")
        repaired = await ai_client.generate_text(
            build_repair_prompt(_coerce_text(raw)[:6000]), max_tokens=token_budget, timeout=60
        )
        data = _parse_response(repaired)
        if isinstance(data, list):
            data = {"mcq_questions": data, "short_questions": []}
    if not isinstance(data, dict):
        raise QuizGenerationError("AI returned an unreadable quiz format.")
    return _normalize_questions(
        data, subject=subject, difficulty=difficulty, study_text=study_text,
        num_mcq=num_mcq, num_short=num_short,
    )
