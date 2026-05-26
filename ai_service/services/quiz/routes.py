import ast
import json
import logging
import re
import unicodedata
from fastapi import APIRouter, HTTPException
from .schemas import QuizQuestion, QuizRequest, QuizResponse
from .prompts import _build_quiz_prompt, _build_repair_prompt

logger = logging.getLogger(__name__)
quiz_router = APIRouter()

try:
    # Prefer relative import when running as a package
    from ...core.ai_client import ai_client
    from ...core.http import get_async_client
except Exception:  # pragma: no cover - fallback paths
    try:
        from core.ai_client import ai_client
        from core.http import get_async_client
    except Exception as e:
        logger.exception("Could not import FastAPI ai_client for quiz: %s", e)
        ai_client = None
        get_async_client = None


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            elif item is not None:
                text = str(item).strip()
                if text:
                    parts.append(text)
        return "\n".join(parts)
    return str(value)


def _strip_fences(text) -> str:
    """
    Strip markdown code fences from LLM responses.
    Handles ```json ... ```, ``` ... ```, and leading/trailing whitespace.
    """
    text = _as_text(text).strip()
    # Remove opening fence: ```json or ```
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    # Remove closing fence
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def _normalize_study_text(text: str) -> str:
    """Normalize OCR/PDF artifacts so prompts are cleaner and more stable."""
    if not text:
        return ""

    cleaned = unicodedata.normalize("NFKC", text)

    replacements = {
        "\u00ad": "",      # soft hyphen
        "\ufeff": "",      # BOM
        "\u200b": "",      # zero-width space
        "\u2011": "-",     # non-breaking hyphen
        "\u2013": "-",
        "\u2014": "-",
        "\ufb01": "fi",    # ligature fi
        "\ufb02": "fl",    # ligature fl
        "\u2212": "-",     # math minus
        "\u00d7": " x ",   # multiply symbol
        "\u00f7": " / ",   # division symbol
    }

    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)

    # Collapse noisy whitespace from slide extraction.
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # Keep prompt within a stable budget to avoid truncated JSON outputs.
    max_chars = 16000
    if len(cleaned) > max_chars:
        logger.info("Study text too long (%s chars), truncating to %s chars", len(cleaned), max_chars)
        cleaned = cleaned[:max_chars]

    return cleaned.strip()


def _parse_json_safe(text, provider_hint: str = "") -> dict | None:
    """
    Robustly parse a JSON string from an LLM response.
    Strips markdown fences, then falls back to finding the first {...} block.
    Returns None if parsing fails entirely.
    """
    source_text = _as_text(text)
    clean = _strip_fences(source_text)

    # Attempt 1: direct parse of cleaned text
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Attempt 2: extract first balanced JSON object/array from noisy text.
    def _extract_balanced_json_block(source: str) -> str | None:
        start = -1
        opener = ""
        for i, ch in enumerate(source):
            if ch in "[{":
                start = i
                opener = ch
                break
        if start == -1:
            return None

        closer = "}" if opener == "{" else "]"
        depth = 0
        in_string = False
        escaped = False

        for i in range(start, len(source)):
            ch = source[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue

            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return source[start : i + 1]

        return None

    extracted = _extract_balanced_json_block(clean)
    if extracted:
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass

    # Attempt 3: ast.literal_eval — handles Python dict literals with single quotes
    # (some providers return {'key': 'val'} instead of {"key": "val"})
    for candidate in ([extracted] if extracted else []) + [clean]:
        try:
            result = ast.literal_eval(candidate)
            if isinstance(result, (dict, list)):
                return result
        except Exception:
            pass

    logger.warning(
        "Could not parse JSON from %s response. First 300 chars: %s",
        provider_hint or "provider",
        source_text[:300],
    )
    return None


@quiz_router.post("/", response_model=QuizResponse)
async def quiz_endpoint(payload: QuizRequest):
    """
    Internal FastAPI endpoint used by Django to generate quizzes via LLM.
    """
    if ai_client is None:
        raise HTTPException(status_code=503, detail="AI service not available")

    normalized_study_text = _normalize_study_text(payload.study_text)
    prompt_payload = QuizRequest(
        subject=payload.subject,
        study_text=normalized_study_text,
        num_mcq=payload.num_mcq,
        num_short=payload.num_short,
        difficulty=payload.difficulty,
    )
    prompt = _build_quiz_prompt(prompt_payload)

    try:
        # Scale max_tokens with quiz size: each MCQ needs ~120 tokens, short ~80.
        # Add 512 overhead for JSON structure. Floor at 2048, cap at 8192.
        estimated_tokens = max(2048, min(8192, (payload.num_mcq * 120) + (payload.num_short * 80) + 512))

        data = None
        client = await get_async_client()
        raw = await ai_client.generate_content(client, prompt, max_tokens=estimated_tokens, timeout=60)

        logger.debug("Quiz provider returned type: %s", type(raw).__name__)

        if isinstance(raw, dict):
            if "choices" in raw and isinstance(raw.get("choices"), list):
                # Azure response format – extract content string from choices
                try:
                    content_str = _as_text(raw["choices"][0].get("message", {}).get("content"))
                    logger.debug("Extracted Azure content (first 100): %s", content_str[:100])
                    data = _parse_json_safe(content_str, provider_hint="Azure")
                    if data is None:
                        # One-shot repair attempt for malformed/truncated JSON-like output.
                        try:
                            repair_raw = await ai_client.generate_content(
                                client,
                                _build_repair_prompt(content_str[:6000]),
                                max_tokens=estimated_tokens,
                                timeout=60,
                            )
                            repair_text = (
                                _as_text(repair_raw.get("choices", [{}])[0].get("message", {}).get("content"))
                                if isinstance(repair_raw, dict)
                                else _as_text(repair_raw)
                            )
                            data = _parse_json_safe(repair_text, provider_hint="Azure-repair")
                        except Exception as repair_exc:
                            logger.warning("Azure repair attempt failed: %s", repair_exc)
                    if data is None:
                        raise HTTPException(status_code=502, detail="Failed to parse Azure response")
                except (KeyError, IndexError) as e:
                    logger.error("Malformed Azure choices structure: %s", e)
                    raise HTTPException(status_code=502, detail="Failed to parse Azure response")
            else:
                # Already a parsed dict (e.g. DeepSeek / Gemini returning clean JSON)
                data = raw
        else:
            # String response – strip fences then parse
            raw_text = str(raw)
            data = _parse_json_safe(raw_text)
            if data is None:
                try:
                    repair_raw = await ai_client.generate_content(
                        client,
                        _build_repair_prompt(raw_text[:6000]),
                        max_tokens=estimated_tokens,
                        timeout=60,
                    )
                    repair_text = (
                        _as_text(repair_raw.get("choices", [{}])[0].get("message", {}).get("content"))
                        if isinstance(repair_raw, dict)
                        else _as_text(repair_raw)
                    )
                    data = _parse_json_safe(repair_text, provider_hint="repair")
                except Exception as repair_exc:
                    logger.warning("Repair attempt failed: %s", repair_exc)
            if data is None:
                raise HTTPException(status_code=502, detail="Invalid quiz format from AI provider")

        # Validate response structure
        mcq_questions = data.get("mcq_questions", []) if data else []
        short_questions = data.get("short_questions", []) if data else []

        if not isinstance(mcq_questions, list):
            mcq_questions = []
        if not isinstance(short_questions, list):
            short_questions = []

        if not mcq_questions and not short_questions:
            logger.warning("Quiz response has no questions. Data: %s", data)
            raise HTTPException(
                status_code=502,
                detail="Quiz response missing both mcq_questions and short_questions",
            )

        def normalize_question(q, q_type):
            if not isinstance(q, dict):
                return None
            return {
                "question": q.get("question", ""),
                "type": q_type,
                "options": q.get("options", []) if q_type == "mcq" else [],
                "answer": q.get("answer", ""),
                "explanation": q.get("explanation", ""),
            }

        normalized_mcq = [
            norm for q in mcq_questions if (norm := normalize_question(q, "mcq"))
        ]
        normalized_short = [
            norm for q in short_questions if (norm := normalize_question(q, "short"))
        ]

        return {
            "subject": payload.subject,
            "study_text": payload.study_text,
            "difficulty": payload.difficulty,
            "mcq_questions": normalized_mcq,
            "short_questions": normalized_short,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in FastAPI quiz endpoint: %s", exc)
        raise HTTPException(status_code=500, detail="Quiz generation error")