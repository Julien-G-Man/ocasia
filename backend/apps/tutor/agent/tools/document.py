"""Agent tool adapter for the shared tutor RAG engine."""

import logging

from apps.tutor.retrieval import rag_engine

logger = logging.getLogger(__name__)


async def search_document(query: str, top_k: int = 5, session_id: str | None = None) -> dict:
    """Search public platform knowledge and this conversation's uploaded documents."""
    if not query.strip():
        return {"chunks": [], "message": "Search query is empty."}
    try:
        chunks = await rag_engine.search(query, top_k=top_k, session_id=session_id)
        return {
            "chunks": chunks,
            "message": "" if chunks else "No relevant passages were found in the indexed tutor corpus.",
        }
    except Exception as exc:
        logger.exception("Tutor RAG retrieval failed")
        return {"chunks": [], "error": str(exc)}
