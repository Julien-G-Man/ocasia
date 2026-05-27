import logging
from fastapi import APIRouter, HTTPException
from .schemas import QuizQuestion, QuizRequest, QuizResponse
from .prompts import _build_quiz_prompt, _build_repair_prompt
from .helpers import _as_text, _strip_fences, _normalize_study_text, _parse_json_safe

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



@quiz_router.post("/", response_model=QuizResponse)
async def quiz_endpoint(payload: QuizRequest):
    """
    Internal FastAPI endpoint used by Django to generate quizzes via LLM.
    """
    print(
        "quiz_endpoint start:",
        {
            "subject": payload.subject,
            "num_mcq": payload.num_mcq,
            "num_short": payload.num_short,
            "difficulty": payload.difficulty,
        },
    )

    if ai_client is None:
        print("quiz_endpoint ai_client unavailable")
        raise HTTPException(status_code=503, detail="AI service not available")

    normalized_study_text = _normalize_study_text(payload.study_text)
    print(
        "quiz_endpoint normalized study text:",
        {"subject": payload.subject, "chars": len(normalized_study_text)},
    )
    prompt_payload = QuizRequest(
        subject=payload.subject,
        study_text=normalized_study_text,
        num_mcq=payload.num_mcq,
        num_short=payload.num_short,
        difficulty=payload.difficulty,
    )
    prompt = _build_quiz_prompt(prompt_payload)

    try:
        # Scale max_tokens with quiz size.
        # Each MCQ needs ~250 tokens (question + 4 options + answer + explanation,
        # including code fences for technical topics). Short answers need ~150.
        # Add 1024 overhead for JSON structure. Floor at 4096, cap at 8192.
        estimated_tokens = max(4096, min(8192, (payload.num_mcq * 250) + (payload.num_short * 150) + 1024))
        print(
            "quiz_endpoint token estimate:",
            {"subject": payload.subject, "estimated_tokens": estimated_tokens},
        )

        data = None
        client = await get_async_client()
        raw = await ai_client.generate_content(client, prompt, max_tokens=estimated_tokens, timeout=60)

        print("quiz_endpoint raw response type:", type(raw).__name__)
        logger.debug("Quiz provider returned type: %s", type(raw).__name__)

        if isinstance(raw, dict):
            if "choices" in raw and isinstance(raw.get("choices"), list):
                # Azure response format – extract content string from choices
                try:
                    content_str = _as_text(raw["choices"][0].get("message", {}).get("content"))
                    print(
                        "quiz_endpoint azure content preview:",
                        {"subject": payload.subject, "preview": content_str[:120]},
                    )
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
                            print("quiz_endpoint azure repair failed:", repair_exc)
                            logger.warning("Azure repair attempt failed: %s", repair_exc)
                    if data is None:
                        print("quiz_endpoint azure parsing failed")
                        raise HTTPException(status_code=502, detail="Failed to parse Azure response")
                except (KeyError, IndexError) as e:
                    print("quiz_endpoint malformed azure choices structure:", e)
                    logger.error("Malformed Azure choices structure: %s", e)
                    raise HTTPException(status_code=502, detail="Failed to parse Azure response")
            else:
                # Already a parsed dict (e.g. DeepSeek / Gemini returning clean JSON)
                data = raw
                print(
                    "quiz_endpoint parsed dict response:",
                    {"subject": payload.subject, "keys": list(data.keys()) if isinstance(data, dict) else []},
                )
        else:
            # String response – strip fences then parse
            raw_text = str(raw)
            print(
                "quiz_endpoint string response preview:",
                {"subject": payload.subject, "preview": raw_text[:120]},
            )
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
                    print("quiz_endpoint repair failed:", repair_exc)
                    logger.warning("Repair attempt failed: %s", repair_exc)
            if data is None:
                print("quiz_endpoint invalid quiz format from provider")
                raise HTTPException(status_code=502, detail="Invalid quiz format from AI provider")

        # Validate response structure
        mcq_questions = data.get("mcq_questions", []) if data else []
        short_questions = data.get("short_questions", []) if data else []

        if not isinstance(mcq_questions, list):
            mcq_questions = []
        if not isinstance(short_questions, list):
            short_questions = []

        print(
            "quiz_endpoint parsed question counts:",
            {
                "subject": payload.subject,
                "mcq_questions": len(mcq_questions),
                "short_questions": len(short_questions),
            },
        )

        if not mcq_questions and not short_questions:
            print("quiz_endpoint returned no questions:", {"subject": payload.subject, "data": data})
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

        print(
            "quiz_endpoint normalized questions:",
            {
                "subject": payload.subject,
                "mcq_questions": len(normalized_mcq),
                "short_questions": len(normalized_short),
            },
        )

        print(
            "quiz_endpoint success:",
            {
                "subject": payload.subject,
                "num_mcq": len(normalized_mcq),
                "num_short": len(normalized_short),
            },
        )

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