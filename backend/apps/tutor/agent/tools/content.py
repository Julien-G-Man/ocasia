import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from apps.tutor.langchain import build_chat_model

logger = logging.getLogger(__name__)


def _parse_json(text: str):
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = min((pos for pos in (cleaned.find("{"), cleaned.find("[")) if pos >= 0), default=-1)
        if start < 0:
            raise
        end = max(cleaned.rfind("}"), cleaned.rfind("]"))
        if end <= start:
            raise
        return json.loads(cleaned[start:end + 1])


async def _invoke_json(system: str, prompt: str):
    model = build_chat_model()
    response = await model.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=prompt),
    ])
    content = response.content
    if not isinstance(content, str):
        content = "\n".join(block.get("text", "") for block in content if isinstance(block, dict))
    try:
        return _parse_json(content)
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning("Tutor model returned malformed JSON; attempting one repair call.")
        repaired = await model.ainvoke([
            SystemMessage(content="Repair the supplied response into valid JSON only. Preserve its data; do not invent missing content."),
            HumanMessage(content=f"Expected output instructions:\n{prompt[:1200]}\n\nMalformed response:\n{content[:12000]}"),
        ])
        repaired_content = repaired.content
        if not isinstance(repaired_content, str):
            repaired_content = "\n".join(
                block.get("text", "") for block in repaired_content if isinstance(block, dict)
            )
        return _parse_json(repaired_content)


async def summarize_text(text: str, max_words: int = 300, focus: str = "") -> dict:
    """Summarize long study material into key points."""
    if not text.strip():
        return {"summary": ""}
    max_words = max(25, min(int(max_words), 1500))
    prompt = (
        f"Summarize the following text in approximately {max_words} words. Return only the summary.\n"
        f"Focus: {focus.strip() or 'main ideas and useful details'}\n\nTEXT:\n{text[:20000]}"
    )
    try:
        response = await build_chat_model().ainvoke([
            SystemMessage(content="You summarize educational material clearly and faithfully."),
            HumanMessage(content=prompt),
        ])
        content = response.content
        summary = content if isinstance(content, str) else str(content)
        return {"summary": summary.strip()}
    except Exception as exc:
        logger.warning("Summarization failed: %s", exc)
        words = text.split()
        return {"summary": " ".join(words[:max_words]) + ("..." if len(words) > max_words else "")}


async def evaluate_answer(question: str, correct_answer: str, user_answer: str) -> dict:
    """Evaluate a student's free-text answer and return a score from zero to one."""
    if not user_answer.strip():
        return {"is_correct": False, "score": 0.0, "reasoning": "No answer provided."}
    prompt = (
        "Evaluate the student's answer for factual accuracy, completeness, and relevance. "
        "Return JSON with is_correct (boolean), score (0 to 1), and reasoning (1-2 sentences).\n\n"
        f"Question: {question}\nCorrect answer: {correct_answer}\nStudent answer: {user_answer}"
    )
    try:
        result = await _invoke_json("You are a fair expert short-answer evaluator. Return valid JSON only.", prompt)
        score = max(0.0, min(float(result.get("score", 0)), 1.0))
        return {
            "is_correct": bool(result.get("is_correct", score >= 0.8)),
            "score": score,
            "reasoning": str(result.get("reasoning", "Evaluation complete.")),
        }
    except Exception as exc:
        logger.warning("Answer evaluation failed; using exact-match fallback: %s", exc)
        correct = user_answer.strip().casefold() == correct_answer.strip().casefold()
        return {
            "is_correct": correct,
            "score": 1.0 if correct else 0.0,
            "reasoning": "Exact-match fallback (AI evaluation unavailable).",
        }


async def _retrieved_study_text(query: str, top_k: int = 8) -> str:
    """Use the shared corpus as fallback context for chat-generated study content."""
    from apps.tutor.retrieval import rag_engine

    passages = await rag_engine.search(query, top_k=top_k)
    return "\n\n".join(
        f"[Source: {item['source']}, page: {item['page']}]\n{item['text']}"
        for item in passages
    )


async def generate_quiz(
    study_text: str = "",
    subject: str = "",
    difficulty: str = "medium",
    num_mcq: int = 5,
    num_short: int = 0,
    source_type: str = "text",
    source_title: str = "",
) -> dict:
    """Pass chat or retrieved context to the quiz-domain AI Engine service."""
    from apps.quiz.services import generate_quiz as quiz_service

    if not subject or not subject.strip():
        raise ValueError("Subject is required.")
    if len((study_text or "").strip()) < 30:
        try:
            study_text = await _retrieved_study_text(subject)
            if study_text:
                source_type = "retrieval"
        except Exception:
            logger.exception("Could not retrieve study context for quiz generation")
            study_text = ""
    if len((study_text or "").strip()) < 30:
        study_text = f"Topic: {subject}\nGenerate questions using established subject-matter knowledge."
        source_type = "text"
    return await quiz_service(
        subject=subject,
        study_text=study_text,
        difficulty=difficulty,
        num_mcq=num_mcq,
        num_short=num_short,
        source_type=source_type,
        source_title=source_title,
    )


async def generate_flashcards(
    text: str = "",
    subject: str = "",
    num_cards: int = 10,
    difficulty: str = "intermediate",
    prompt: str = "",
) -> dict:
    """Pass chat or retrieved context to the flashcard-domain AI Engine service."""
    from apps.flashcards.services import generate_flashcards as flashcard_service

    if not subject or not subject.strip():
        raise ValueError("Subject is required.")
    if len((text or "").strip()) < 30:
        try:
            text = await _retrieved_study_text(subject)
        except Exception as exc:
            logger.exception("Could not retrieve study context for flashcard generation")
            raise ValueError("Could not access indexed study materials. Provide the study text directly.") from exc
    if len((text or "").strip()) < 30:
        raise ValueError("Provide study material or an indexed document topic to create flashcards.")
    return await flashcard_service(
        text=text,
        subject=subject,
        num_cards=num_cards,
        difficulty=difficulty,
        prompt=prompt,
    )

async def explain_concept(question: str, answer: str) -> dict:
    """Give a beginner-friendly explanation of a question and its answer."""
    response = await build_chat_model().ainvoke([
        SystemMessage(content="You are a friendly tutor. Explain clearly to a beginner in three short sentences."),
        HumanMessage(content=f"Question: {question}\nCorrect answer: {answer}\nExplain the concept."),
    ])
    content = response.content
    return {"explanation": (content if isinstance(content, str) else str(content)).strip()}


async def request_quiz_form(topic: str = "") -> dict:
    """Signal that the student wants to open the inline quiz setup form."""
    return {"status": "quiz_form_shown", "topic": topic}
