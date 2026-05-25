from abc import ABC, abstractmethod


class KBSearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, top_k: int = 4) -> list[dict]:
        """
        Return up to top_k chunks relevant to query.
        Each dict: {chunk_id, heading, source_file, keywords, text, score}
        """

    def get_context(self, query: str, top_k: int = 4, max_chars: int = 2800) -> str:
        results = self.search(query, top_k=top_k)
        parts: list[str] = []
        total = 0
        for r in results:
            block = f"[{r.get('source_file', '')} > {r.get('heading', '')}]\n{r.get('text', '').strip()}"
            if parts and total + len(block) > max_chars:
                break
            parts.append(block)
            total += len(block)
        return "\n\n".join(parts)
