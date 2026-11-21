"""Quiz-domain services backed by Django's in-process AI engine."""

import json
import logging
import random
import re
import unicodedata
from datetime import datetime
from time import perf_counter

from asgiref.sync import sync_to_async
from django.core.cache import cache
from django.utils import timezone

from apps.core.ai_engine import ai_client
from apps.core.ai_engine.utils import _coerce_text, _extract_json_substring
from apps.quiz.models import QuizSession, QuizTopicSchedule, TopicPerformance
from apps.quiz.prompts import (
    build_quiz_prompt,
    build_repair_prompt,
    build_short_answer_prompt,
)
from apps.quiz.utils.latency import record_ai_latency
from apps.quiz.utils.scheduling import update_quiz_schedule, update_topic_performance
from apps.quiz.utils.scoring import format_mcq_answer

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
        logger.warning(
            "Quiz provider returned fewer valid questions than requested (mcq=%d/%d short=%d/%d).",
            len(mcq), num_mcq, len(short), num_short,
        )
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
    if difficulty == "random":
        difficulty = random.choice(("easy", "medium", "hard"))
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

    started = perf_counter()
    raw = await ai_client.generate_text(prompt, max_tokens=token_budget, timeout=60)
    await record_ai_latency("quiz", int((perf_counter() - started) * 1000))

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


async def evaluate_short_answer(question: str, correct_answer: str, user_answer: str) -> dict:
    """Grade a free-text answer; falls back to exact match if the AI is unavailable."""
    if not user_answer.strip():
        return {"is_correct": False, "score": 0.0, "reasoning": "No answer provided."}

    prompt = build_short_answer_prompt(question, correct_answer, user_answer)

    try:
        raw = await ai_client.generate_text(prompt, max_tokens=512, timeout=30)
        result = _parse_response(raw)
        if not isinstance(result, dict):
            raise ValueError("Evaluator returned invalid JSON")
        score = max(0.0, min(float(result.get("score", 0)), 1.0))
        return {
            "is_correct": bool(result.get("is_correct", score >= 0.8)),
            "score": score,
            "reasoning": str(result.get("reasoning", "Evaluation complete.")),
        }
    except Exception as exc:
        logger.warning("Short-answer evaluation failed; using exact-match fallback: %s", exc)
        correct = user_answer.strip().casefold() == correct_answer.strip().casefold()
        return {
            "is_correct": correct,
            "score": 1.0 if correct else 0.0,
            "reasoning": "Exact-match fallback (AI evaluation unavailable).",
        }


async def submit_quiz(
    *,
    user,
    quiz_data: dict,
    user_answers: dict,
    quiz_id: str | None = None,
    duration_minutes: int = 0,
    time_limit: int = 0,
    exam_mode: bool = False,
) -> dict:
    """Score a quiz, persist the session, and update performance/schedule data."""
    mcq_questions = quiz_data.get("mcq_questions", []) or []
    short_questions = quiz_data.get("short_questions", []) or []
    all_questions = list(mcq_questions) + list(short_questions)
    if not all_questions:
        raise ValueError("No questions found in quiz data")

    total_questions = len(all_questions)
    correct_count = 0
    details = []

    for idx, question in enumerate(all_questions):
        user_answer = str(user_answers.get(str(idx), "")).strip()
        correct_answer = str(question.get("answer", "")).strip()
        options = question.get("options", []) or []
        is_mcq = question.get("type") == "mcq" or bool(options)

        if is_mcq:
            user_letter = user_answer.upper()[:1] if user_answer else ""
            correct_letter = correct_answer.upper()[:1] if correct_answer else ""
            is_correct = bool(user_letter) and user_letter == correct_letter
            reasoning = (
                "MCQ evaluation: Answer letter matched"
                if is_correct
                else "MCQ evaluation: Answer letter did not match"
            )
        else:
            evaluation = await evaluate_short_answer(
                question.get("question", ""), correct_answer, user_answer
            )
            is_correct = evaluation["is_correct"]
            reasoning = evaluation["reasoning"]

        if is_correct:
            correct_count += 1

        details.append({
            "question_index": idx,
            "question": question.get("question", ""),
            "options": options,
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "user_answer_display": format_mcq_answer(user_answer, options) if is_mcq else user_answer,
            "correct_answer_display": format_mcq_answer(correct_answer, options) if is_mcq else correct_answer,
            "is_correct": is_correct,
            "explanation": question.get("explanation", ""),
            "reasoning": reasoning,
        })

    score_percent = round((correct_count / total_questions) * 100, 1) if total_questions else 0.0
    results = {
        "quiz_id": quiz_id,
        "subject": quiz_data.get("subject", "Unknown"),
        "difficulty": quiz_data.get("difficulty", "medium"),
        "source_filename": quiz_data.get("source_filename", ""),
        "score": correct_count,
        "total": total_questions,
        "score_percent": score_percent,
        "details": details,
        "submitted_at": datetime.now(),
    }

    subject_clean = (quiz_data.get("subject", "General") or "General")[:100]
    await sync_to_async(QuizSession.objects.create, thread_sensitive=True)(
        user=user,
        subject=subject_clean,
        total_questions=total_questions,
        correct_answers=correct_count,
        score_percentage=score_percent,
        duration_minutes=duration_minutes,
        questions_data=quiz_data,
        user_answers=user_answers,
        exam_mode=exam_mode,
        time_limit_minutes=time_limit or None,
    )

    uid = user.id
    await sync_to_async(cache.delete_many)(
        [
            f"quiz:hist:{uid}", f"quiz:weak:{uid}", f"quiz:due:{uid}",
            f"dash:stats:{uid}", "admin:stats",
        ]
    )

    try:
        await update_topic_performance(user, subject_clean, correct_count, total_questions)
    except Exception as exc:
        logger.warning("TopicPerformance update failed: %s", exc)

    try:
        await update_quiz_schedule(user, subject_clean, score_percent)
    except Exception as exc:
        logger.warning("QuizTopicSchedule update failed: %s", exc)

    logger.info(
        "Quiz submitted: %d/%d correct (%s%%)", correct_count, total_questions, score_percent
    )
    return results


def list_history(user) -> dict:
    cache_key = f"quiz:hist:{user.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    sessions = QuizSession.objects.filter(user=user).order_by("-created_at")[:20]
    result = {
        "history": [
            {
                "id": s.id,
                "subject": s.subject,
                "total_questions": s.total_questions,
                "correct_answers": s.correct_answers,
                "score_percent": float(s.score_percentage),
                "created_at": s.created_at.isoformat(),
                "exam_mode": s.exam_mode,
            }
            for s in sessions
        ]
    }
    cache.set(cache_key, result, timeout=60)
    return result


def get_replay(user, session_id) -> dict:
    session = QuizSession.objects.get(id=session_id, user=user)
    return {"quiz_data": session.questions_data}


def list_weak_areas(user) -> dict:
    cache_key = f"quiz:weak:{user.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    weak = TopicPerformance.objects.filter(
        user=user,
        total_questions__gte=3,
    ).order_by("accuracy")[:5]
    result = {
        "weak_areas": [
            {
                "topic": tp.topic,
                "subject": tp.subject,
                "total_questions": tp.total_questions,
                "correct_answers": tp.correct_answers,
                "accuracy": round(tp.accuracy, 1),
                "last_attempted": tp.last_attempted.isoformat(),
            }
            for tp in weak
        ]
    }
    cache.set(cache_key, result, timeout=120)
    return result


def list_due_topics(user) -> dict:
    cache_key = f"quiz:due:{user.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    due = QuizTopicSchedule.objects.filter(
        user=user,
        next_review__lte=timezone.now(),
    ).order_by("next_review")
    result = {
        "due_topics": [
            {
                "topic": s.topic,
                "subject": s.subject,
                "next_review": s.next_review.isoformat(),
                "last_review": s.last_review.isoformat() if s.last_review else None,
                "interval": s.interval,
            }
            for s in due
        ]
    }
    cache.set(cache_key, result, timeout=60)
    return result
