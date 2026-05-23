"""
MCP Tool: summarize_text

Condenses a body of text into key points. Used by the AI when it needs
to reduce a large document before passing it to another tool (e.g.,
generate_quiz or generate_flashcards) that has a tighter token budget.
"""

import logging

logger = logging.getLogger(__name__)

from core.ai_client import ai_service
from core.http import get_async_client


async def summarize_text(
    text: str,
    max_words: int = 300,
    focus: str = "",
) -> dict:
    """
    Returns:
        {"summary": str}

    Args:
        text:      Content to summarize (will be truncated to 20 000 chars).
        max_words: Target length of the summary in words.
        focus:     Optional instruction to direct the summary
                   (e.g. "focus on definitions and key terms").
    """
    if not text.strip():
        return {"summary": ""}

    # Hard-cap input so we don't blow the token budget
    truncated = text[:20_000]
    if len(text) > 20_000:
        logger.debug("[mcp:summarize] input truncated from %d to 20000 chars", len(text))

    focus_line = f"\nFocus: {focus.strip()}" if focus.strip() else ""

    prompt = f"""Summarize the following text in approximately {max_words} words.
Return only the summary — no preamble, no labels.{focus_line}

TEXT:
{truncated}"""

    try:
        client = await get_async_client()
        # max_tokens: ~1.5 tokens per word, rounded up with headroom
        max_tokens = min(2048, max(256, int(max_words * 2)))
        raw = await ai_service.generate_content(client=client, prompt=prompt, max_tokens=max_tokens, timeout=30)

        summary = raw.strip() if isinstance(raw, str) else str(raw).strip()
        logger.debug("[mcp:summarize] done words=%d", len(summary.split()))
        return {"summary": summary}

    except Exception as exc:
        logger.warning("[mcp:summarize] AI call failed: %s", exc)
        # Graceful degradation: return a truncated version of the raw text
        words = text.split()
        fallback = " ".join(words[: max_words]) + ("..." if len(words) > max_words else "")
        return {"summary": fallback}
