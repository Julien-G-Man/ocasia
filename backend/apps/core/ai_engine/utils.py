import json

def _coerce_text(value) -> str:
    """Normalize provider content blocks into plain text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
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
        return "\n".join(parts).strip()
    return str(value).strip()


def _extract_json_substring(text: str):
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    if text.startswith('{') or text.startswith('['):
        try:
            return json.loads(text)
        except Exception:
            pass

    first_brace = min(
        [idx for idx in (text.find('{'), text.find('[')) if idx != -1],
        default=-1
    )
    if first_brace == -1:
        return None

    opening = text[first_brace]
    closing = '}' if opening == '{' else ']'
    last_close = text.rfind(closing)
    if last_close == -1 or last_close <= first_brace:
        return None

    candidate = text[first_brace:last_close + 1]
    try:
        return json.loads(candidate)
    except Exception:
        return None
