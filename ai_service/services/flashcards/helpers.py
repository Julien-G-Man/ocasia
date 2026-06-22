import json
import re

# Keys AI models use to wrap the card list
_CARD_WRAPPER_KEYS = ("cards", "flashcards", "items", "data", "results", "questions")


def _normalize_cards(raw):
    """Normalize raw AI output into [{question, answer}] list."""
    if isinstance(raw, list):
        out = []
        for item in raw:
            if isinstance(item, dict):
                q = (item.get("question") or item.get("front") or "").strip()
                a = (item.get("answer") or item.get("back") or "").strip()
                if q and a:
                    out.append({"question": q[:2000], "answer": a[:4000]})
        return out

    if isinstance(raw, dict):
        # Try known wrapper keys first, then fall back to the first list-valued key.
        for key in _CARD_WRAPPER_KEYS:
            if key in raw and isinstance(raw[key], list):
                return _normalize_cards(raw[key])
        for value in raw.values():
            if isinstance(value, list) and value:
                result = _normalize_cards(value)
                if result:
                    return result
        return []

    if isinstance(raw, str):
        # Try full JSON parse first.
        try:
            parsed = json.loads(raw)
            return _normalize_cards(parsed)
        except Exception:
            pass

        # Strip markdown code fences and retry.
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE).strip()
        if stripped != raw.strip():
            try:
                parsed = json.loads(stripped)
                return _normalize_cards(parsed)
            except Exception:
                pass

        # Try extracting JSON array from mixed text.
        match = re.search(r"\[[\s\S]*\]", raw)
        if match:
            try:
                parsed = json.loads(match.group(0))
                return _normalize_cards(parsed)
            except Exception:
                pass

    return []

