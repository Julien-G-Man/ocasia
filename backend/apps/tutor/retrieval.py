"""Hybrid vector and BM25 retrieval over the pre-indexed tutor corpus."""

from __future__ import annotations

import math
import re
import os
import threading
from hashlib import sha256
from pathlib import Path
from collections import Counter

from asgiref.sync import sync_to_async
from django.conf import settings


class RAGEngine:
    """Retrieve passages from Django's pre-indexed pgvector corpus.

    Indexing is deliberately separate (see ``index_rag_documents``). Search
    combines pgvector cosine similarity with BM25 lexical ranking using
    reciprocal-rank fusion, which avoids mixing incomparable raw scores.
    """

    def __init__(self, *, embedding_model: str = "text-embedding-3-small", candidate_limit: int = 100):
        self.embedding_model = embedding_model
        self.candidate_limit = candidate_limit
        self._embeddings = None
        self._embeddings_lock = threading.Lock()
        self._platform_kb_lock = threading.Lock()

    @property
    def embeddings(self):
        if self._embeddings is None:
            with self._embeddings_lock:
                if self._embeddings is None:
                    from langchain_openai import OpenAIEmbeddings

                    api_key = getattr(settings, "OPENAI_API_KEY", None)
                    if not api_key:
                        raise RuntimeError("OPENAI_API_KEY must be configured for tutor retrieval.")
                    self._embeddings = OpenAIEmbeddings(api_key=api_key, model=self.embedding_model)
        return self._embeddings

    def index_platform_knowledge(self) -> int:
        """Index missing or changed platform KB files during app startup."""
        from apps.tutor.models import TutorDocument
        from apps.tutor.rag_indexing import index_document_bytes, source_key_for_path

        kb_dir = Path(os.environ.get("KB_FILE_PATH") or (Path(__file__).resolve().parent / "platform_kb"))
        if not kb_dir.is_dir():
            raise FileNotFoundError(f"Tutor platform knowledge directory not found: {kb_dir}")

        indexed = 0
        # Guard startup/concurrent first searches so the same KB files are not
        # embedded multiple times within a Django process.
        with self._platform_kb_lock:
            for path in sorted(kb_dir.rglob("*")):
                if not path.is_file() or path.suffix.casefold() not in {".md", ".txt"}:
                    continue
                payload = path.read_bytes()
                source_key = source_key_for_path(path)
                digest = sha256(payload).hexdigest()
                current = TutorDocument.objects.filter(source_key=source_key).only(
                    "content_sha256", "index_version"
                ).first()
                from apps.tutor.rag_indexing import INDEX_VERSION

                if current and current.content_sha256 == digest and current.index_version == INDEX_VERSION:
                    continue
                relative_name = path.relative_to(kb_dir).as_posix()
                index_document_bytes(
                    source_key=source_key,
                    source_name=relative_name,
                    filename=path.name,
                    file_bytes=payload,
                    embeddings=self.embeddings,
                    source_metadata={"source_type": "platform_kb", "relative_path": relative_name},
                )
                indexed += 1
        return indexed

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return re.findall(r"[\w]+", text.casefold(), flags=re.UNICODE)

    @staticmethod
    def _passage_key(text: str) -> str:
        """Normalize passage text so copies with different whitespace dedupe."""
        return " ".join(text.casefold().split())

    @classmethod
    def _bm25(cls, query: str, documents: list[dict], *, k1: float = 1.5, b: float = 0.75) -> list[dict]:
        """Rank the indexed corpus with BM25 (Robertson/Sparck Jones IDF)."""
        query_terms = set(cls._tokens(query))
        if not query_terms or not documents:
            return []
        tokenized = [cls._tokens(item["content"]) for item in documents]
        frequencies = [Counter(tokens) for tokens in tokenized]
        document_frequency = Counter(
            term for counts in frequencies for term in query_terms if counts.get(term, 0)
        )
        average_length = sum(map(len, tokenized)) / len(tokenized) or 1.0
        total = len(documents)
        ranked = []
        for item, tokens, counts in zip(documents, tokenized, frequencies):
            score = 0.0
            length = len(tokens)
            for term in query_terms:
                tf = counts.get(term, 0)
                if not tf:
                    continue
                df = document_frequency[term]
                idf = math.log(1 + (total - df + 0.5) / (df + 0.5))
                score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * length / average_length))
            if score:
                ranked.append((score, item))
        return [item for _, item in sorted(ranked, key=lambda pair: pair[0], reverse=True)]

    @staticmethod
    def _hybrid_search(
        query_vector: list[float], query: str, limit: int, candidate_limit: int, source_type: str | None
    ) -> list[dict]:
        from pgvector.django import CosineDistance

        from apps.tutor.models import TutorDocumentChunk

        chunks = TutorDocumentChunk.objects.select_related("document")
        if source_type:
            chunks = chunks.filter(metadata__source_type=source_type)
        vector_rows = list(
            chunks
            .annotate(distance=CosineDistance("embedding", query_vector))
            .order_by("distance")[:candidate_limit]
            .values("id", "content", "page_number", "metadata", "document__source_name", "document__file_type", "distance")
        )
        # BM25 needs corpus-wide document frequency and average document length.
        corpus = list(
            chunks
            .values("id", "content", "page_number", "metadata", "document__source_name", "document__file_type")
        )
        lexical_rows = RAGEngine._bm25(query, corpus)
        fused: dict[int, tuple[float, dict]] = {}
        rrf_constant = 60
        for rank, row in enumerate(vector_rows, 1):
            fused[row["id"]] = (1 / (rrf_constant + rank), row)
        for rank, row in enumerate(lexical_rows[:candidate_limit], 1):
            score = 1 / (rrf_constant + rank)
            prior, _ = fused.get(row["id"], (0.0, row))
            fused[row["id"]] = (prior + score, row)
        results = []
        seen_passages = set()
        for hybrid_score, row in sorted(fused.values(), key=lambda item: item[0], reverse=True):
            passage_key = RAGEngine._passage_key(row["content"])
            if not passage_key or passage_key in seen_passages:
                continue
            seen_passages.add(passage_key)
            distance = row.get("distance")
            results.append({
                "text": row["content"],
                "source": row["document__source_name"],
                "file_type": row["document__file_type"],
                "page": row["page_number"],
                "similarity": round(1.0 - float(distance), 4) if distance is not None else None,
                "hybrid_score": round(hybrid_score, 6),
                "metadata": row["metadata"] or {},
            })
            if len(results) >= limit:
                break
        return results

    async def search(self, query: str, *, top_k: int = 5, source_type: str | None = None) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        query_vector = await self.embeddings.aembed_query(query)
        return await sync_to_async(self._hybrid_search, thread_sensitive=True)(
            query_vector, query, max(1, min(int(top_k), 20)), self.candidate_limit, source_type
        )


rag_engine = RAGEngine()
