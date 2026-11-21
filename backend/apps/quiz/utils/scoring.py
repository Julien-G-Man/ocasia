"""Pure scoring helpers for quiz answers."""


def format_mcq_answer(answer_value: str, options: list) -> str:
    """Render an MCQ answer as ``"A. Option text"`` when options are available."""
    if not answer_value:
        return ""

    normalized = answer_value.strip()
    if not options:
        return normalized

    letter = normalized.upper()[0]
    option_index = ord(letter) - ord("A")
    if 0 <= option_index < len(options):
        return f"{letter}. {options[option_index]}"

    for option_index, option_text in enumerate(options):
        if normalized.lower() == str(option_text).strip().lower():
            return f"{chr(ord('A') + option_index)}. {option_text}"

    return normalized


def score_to_sm2_quality(score_percent: float) -> int:
    """Map a quiz score percentage to an SM-2 quality rating (0-5)."""
    if score_percent >= 90:
        return 5
    if score_percent >= 75:
        return 4
    if score_percent >= 60:
        return 3
    if score_percent >= 40:
        return 2
    if score_percent >= 20:
        return 1
    return 0
