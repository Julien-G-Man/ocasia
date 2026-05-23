"""
MCP Tool: evaluate_answer

LLM-based short-answer evaluator. Given a question, the correct answer,
and the student's answer, returns a score (0.0-1.0), a boolean, and
brief reasoning.

Extracted from apps/quiz/async_views._evaluate_short_answer and ported
to call ai_service directly (no HTTP round-trip).
"""

import json
import logging

logger = logging.getLogger(__name__)

from core.ai_client import ai_service
from core.http import get_async_client


async def evaluate_answer(
    question: str,
    correct_answer: str,
    user_answer: str,
) -> dict:
    """
    Returns:
        {
            "is_correct": bool,
            "score": float,       # 0.0 – 1.0
            "reasoning": str,
        }
    Falls back to exact-string comparison when the AI is unavailable.
    """
    if not user_answer.strip():
        logger.debug("[mcp:evaluate] empty user_answer — scoring 0")
        return {"is_correct": False, "score": 0.0, "reasoning": "No answer provided."}

    prompt = f"""You are an expert quiz evaluator. Evaluate the student answer below.

Question: {question}

Correct answer: {correct_answer}

Student answer: {user_answer}

Criteria:
1. Factual accuracy
2. Completeness (key points covered)
3. Clarity and relevance

Return ONLY valid JSON — no markdown, no code blocks:
{{"is_correct": true/false, "score": 0.0-1.0, "reasoning": "1-2 sentences"}}"""

    try:
        client = await get_async_client()
        raw = await ai_service.generate_content(client=client, prompt=prompt, max_tokens=150, timeout=20)

        text = raw if isinstance(raw, str) else json.dumps(raw)
        # Strip markdown fences if present
        text = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()

        parsed = json.loads(text)
        result = {
            "is_correct": bool(parsed.get("is_correct", False)),
            "score": float(parsed.get("score", 0.0)),
            "reasoning": str(parsed.get("reasoning", "Evaluation complete.")),
        }
        logger.debug(
            "[mcp:evaluate] is_correct=%s score=%.2f",
            result["is_correct"], result["score"],
        )
        return result

    except json.JSONDecodeError as exc:
        logger.warning("[mcp:evaluate] JSON parse failed: %s. Raw: %.200s", exc, text if "text" in dir() else "")
    except Exception as exc:
        logger.warning("[mcp:evaluate] AI call failed: %s — falling back to string match", exc)

    # Fallback: exact string comparison
    is_correct = user_answer.strip().lower() == correct_answer.strip().lower()
    return {
        "is_correct": is_correct,
        "score": 1.0 if is_correct else 0.0,
        "reasoning": "String match (AI unavailable)." if is_correct else "Answer did not match (AI unavailable).",
    }
