"""Agent tool adapter for the shared tutor RAG engine."""

import logging

from apps.tutor.retrieval import rag_engine

logger = logging.getLogger(__name__)


async def search_document(query: str, top_k: int = 5) -> dict:
    """Search the indexed tutor corpus with hybrid vector and BM25 retrieval."""
    if not query.strip():
        return {"chunks": [], "message": "Search query is empty."}
    try:
        chunks = await rag_engine.search(query, top_k=top_k)
        return {
            "chunks": chunks,
            "message": "" if chunks else "No relevant passages were found in the indexed tutor corpus.",
        }
    except Exception as exc:
        logger.exception("Tutor RAG retrieval failed")
        return {"chunks": [], "error": str(exc)}
