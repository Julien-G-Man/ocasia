"""
agent/tools/flashcards.py — Flashcard generation and concept explanation tool handlers.

Extracted from registry.py to keep each tool's logic in its own file.
All handlers are registered in agent/registry.py and called by agent/executor.py.

Handlers in this file
---------------------
_generate_flashcards_handler — Generates question/answer flashcard pairs via LLM
                               from arbitrary study text. Delegates card normalisation
                               to the flashcards service layer to stay in sync with
                               the standalone /flashcards/ endpoint.
_explain_concept_handler     — Produces a short tutor-style explanation for a flashcard
                               that a student is struggling with. Used by the Flashcard
                               study page "Explain" action.
"""


async def _generate_flashcards_handler(
    text: str,
    subject: str,
    num_cards: int = 10,
    difficulty: str = "intermediate",
    prompt: str = "",
) -> dict:
    """
    Generate flashcard pairs (question / answer) from study text.

    Delegates card parsing and normalisation to `services.flashcards.routes._normalize_cards`
    so the agent and the standalone /flashcards/ HTTP endpoint produce identical output shapes.

    Parameters
    ----------
    text : str
        Study material to extract cards from. Truncated to 16 000 chars in the prompt.
    subject : str
        Topic label included in the prompt for context.
    num_cards : int
        Number of flashcards to generate. Clamped to 1–30.
    difficulty : str
        Difficulty level passed to `DIFFICULTY_PROMPTS` (e.g. "beginner", "intermediate",
        "advanced"). Unknown values fall back to "intermediate".
    prompt : str
        Optional additional instruction appended to the LLM prompt (e.g. "focus on
        definitions only"). Empty string is a no-op.

    Returns
    -------
    dict with key:
        cards : list of {question: str, answer: str}

    Raises
    ------
    ValueError
        If the AI returns a response that cannot be parsed into the expected card format.
    """
    from services.flashcards.routes import _normalize_cards
    from services.flashcards.prompts import DIFFICULTY_PROMPTS
    from core.ai_client import ai_client
    from core.http import get_async_client

    num_cards = max(1, min(int(num_cards), 30))
    difficulty_prompt = DIFFICULTY_PROMPTS.get(difficulty, DIFFICULTY_PROMPTS.get("intermediate", ""))

    full_prompt = (
        f"You are an expert study assistant.\n\n"
        f"Subject: {subject}\n\n"
        f"Content:\n{text[:16000]}\n\n"
        f"Additional instructions:\n{prompt}\n\n"
        f"Difficulty level:\n{difficulty_prompt}\n\n"
        f"Create {num_cards} flashcards.\n\n"
        f'Return ONLY valid JSON:\n[{{"question": "...", "answer": "..."}}]'
    )

    client = await get_async_client()
    raw = await ai_client.generate_content(client=client, prompt=full_prompt, max_tokens=1200, timeout=30)
    cards = _normalize_cards(raw)
    if not cards:
        raise ValueError("AI returned an unreadable flashcard format.")
    return {"cards": cards}


async def _explain_concept_handler(question: str, answer: str) -> dict:
    """
    Generate a short tutor-style explanation for a flashcard a student is struggling with.

    Called by the Flashcard study page when the student taps "Explain this".
    Kept deliberately brief (3 sentences, beginner-friendly) to avoid overwhelming the student.

    Parameters
    ----------
    question : str
        The flashcard question text.
    answer : str
        The correct answer text.

    Returns
    -------
    dict with key:
        explanation : str  — 2–4 sentence plain-language explanation.
    """
    from core.ai_client import ai_client
    from core.http import get_async_client

    full_prompt = (
        f"A student is struggling with this flashcard.\n\n"
        f"Question: {question}\n"
        f"Correct Answer: {answer}\n\n"
        f"Explain this concept clearly in 3 short sentences like a tutor helping a beginner."
    )
    client = await get_async_client()
    raw = await ai_client.generate_content(client=client, prompt=full_prompt, max_tokens=250, timeout=20)
    explanation = raw.strip() if isinstance(raw, str) else str(raw).strip()
    return {"explanation": explanation}
