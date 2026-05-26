import re
import ast
import json
import logging
import unicodedata

logger = logging.getLogger(__name__)

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
