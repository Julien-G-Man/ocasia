import json
import logging
import re
from pathlib import Path

from kb.base import KBSearchProvider

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-z0-9]{2,}")


class TFIDFProvider(KBSearchProvider):
    """
    Token-overlap KB search. No vector math — fast and free.
    Scoring: token overlap + keyword phrase match (+3) + substring (+2.5) + heading token (+1.5).
    """

    def __init__(self, kb_file: Path) -> None:
        self._chunks: dict[str, dict] = {}
        self._token_index: dict[str, list[str]] = {}
        self._loaded = False
        self._load(kb_file)

    def search(self, query: str, top_k: int = 4) -> list[dict]:
        if not self._loaded or not self._chunks:
            return []

        query_l = query.lower()
        query_tokens = _WORD_RE.findall(query_l)

        scores: dict[str, float] = {}
        for token in query_tokens:
            for chunk_id in self._token_index.get(token, []):
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0

        for chunk_id, data in self._chunks.items():
            chunk_keywords = [kw.lower() for kw in data.get("keywords", [])]
            for kw in chunk_keywords:
                if kw in query_l:
                    scores[chunk_id] = scores.get(chunk_id, 0.0) + 3.0
            if query_l in data.get("text", "").lower():
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 2.5
            heading_l = data.get("heading", "").lower()
            if any(tok in heading_l for tok in query_tokens):
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.5

        if not scores:
            return []

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        for chunk_id, score in ranked[:top_k]:
            data = self._chunks[chunk_id]
            results.append({
                "chunk_id": chunk_id,
                "heading": data.get("heading", ""),
                "source_file": data.get("source_file", ""),
                "keywords": data.get("keywords", []),
                "text": data.get("text", ""),
                "score": round(score, 2),
            })
        return results

    def _load(self, kb_file: Path) -> None:
        if not kb_file.exists():
            logger.warning("[kb:tfidf] knowledge file not found: %s", kb_file)
            return
        try:
            raw = json.loads(kb_file.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("[kb:tfidf] failed to load %s", kb_file)
            return

        chunks: dict[str, dict] = {}
        for chunk_id, value in raw.items():
            if chunk_id.startswith("_") or not isinstance(value, dict) or "text" not in value:
                continue
            chunks[chunk_id] = value

        if not chunks:
            logger.warning("[kb:tfidf] no content chunks found in %s", kb_file)
            return

        self._chunks = chunks
        self._build_index()
        self._loaded = True
        logger.info("[kb:tfidf] loaded %d chunks from %s", len(chunks), kb_file)

    def _build_index(self) -> None:
        index: dict[str, list[str]] = {}
        for chunk_id, data in self._chunks.items():
            token_set = set(_WORD_RE.findall((data.get("text", "") + " " + data.get("heading", "")).lower()))
            for kw in data.get("keywords", []):
                token_set.update(_WORD_RE.findall(kw.lower()))
            for token in token_set:
                index.setdefault(token, []).append(chunk_id)
        self._token_index = index
