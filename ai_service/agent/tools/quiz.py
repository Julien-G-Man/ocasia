"""
agent/tools/quiz.py — Quiz generation tool handlers.

Extracted from registry.py to keep each tool's logic in its own file.
All handlers are registered in agent/registry.py and called by agent/executor.py.

Handlers in this file
---------------------
_generate_quiz_handler       — Generates MCQ/short-answer questions via LLM.
                               Used by both the in-agent `generate_quiz` tool and
                               the standalone `/agent/quiz/generate/` endpoint.
_request_quiz_form_handler   — No-op signal tool. Returns immediately without an LLM call.
                               Its sole purpose is to let the AI signal quiz intent;
                               the router captures the call and sets action='show_quiz_form'
                               in the HTTP response so React renders the inline quiz-param card.
"""


async def _generate_quiz_handler(
    study_text: str,
    subject: str,
    difficulty: str = "medium",
    num_mcq: int = 5,
    num_short: int = 0,
) -> dict:
    """
    Generate quiz questions for a given subject and study text.

    Delegates prompt construction and JSON parsing to the quiz service layer
    (services/quiz/routes.py) so the two code paths stay in sync.

    Parameters
    ----------
    study_text : str
        Source material to base questions on (truncated to 16 000 chars internally).
    subject : str
        Topic label shown in quiz results and difficulty auto-determination.
    difficulty : "easy" | "medium" | "hard"
        Clamped to the allowed set; defaults to "medium" for unknown values.
    num_mcq : int
        Number of multiple-choice questions. Clamped to 1–20.
    num_short : int
        Number of short-answer questions. Clamped to 0–5.

    Returns
    -------
    dict with keys:
        mcq_questions   : list of {question, options, answer, explanation}
        short_questions : list of {question, answer, explanation}
        subject         : str
        difficulty      : str

    Raises
    ------
    ValueError
        If the AI returns a response that cannot be parsed into the expected structure.
    """
    from services.quiz.routes import _normalize_study_text, _parse_json_safe
    from services.quiz.prompts import _build_quiz_prompt
    from services.quiz.schemas import QuizRequest
    from core.ai_client import ai_client
    from core.http import get_async_client

    num_mcq = max(1, min(int(num_mcq), 20))
    num_short = max(0, min(int(num_short), 5))
    difficulty = difficulty.lower() if difficulty.lower() in ("easy", "medium", "hard") else "medium"

    payload = QuizRequest(
        subject=subject,
        study_text=_normalize_study_text(study_text),
        num_mcq=num_mcq,
        num_short=num_short,
        difficulty=difficulty,
    )
    prompt = _build_quiz_prompt(payload)
    estimated_tokens = max(2048, min(8192, num_mcq * 120 + num_short * 80 + 512))

    client = await get_async_client()
    raw = await ai_client.generate_content(client=client, prompt=prompt, max_tokens=estimated_tokens, timeout=60)

    text = raw if isinstance(raw, str) else str(raw)
    data = _parse_json_safe(text)
    if not data:
        raise ValueError("AI returned an unreadable quiz format.")

    return {
        "mcq_questions": data.get("mcq_questions", []),
        "short_questions": data.get("short_questions", []),
        "subject": subject,
        "difficulty": difficulty,
    }


async def _request_quiz_form_handler(topic: str = "") -> dict:
    """
    No-op signal tool — returns immediately without any LLM call.

    The agent calls this when it detects quiz intent in the user's message.
    The router (`agent/router.py`) intercepts the output and sets:
        side_data["action"]  = "show_quiz_form"
        side_data["prefill"] = {"topic": topic}

    These are forwarded through Django to React, which renders the inline
    quiz-param card (QuizFormCard) pre-filled with the extracted topic.
    The actual quiz generation happens only after the user submits the form.

    Parameters
    ----------
    topic : str
        Topic string extracted from the conversation by the agent. May be empty
        if the user did not specify one; the frontend will leave the field blank.

    Returns
    -------
    dict
        {"status": "quiz_form_shown", "topic": topic}
    """
    return {"status": "quiz_form_shown", "topic": topic}
