"""
Document search tool for RAG-enabled chat sessions.

`make_search_document_handler(session_id)` returns a handler pre-bound to
a specific session. The handler is injected into the agent loop only when
the session has a document (has_document=True). It is never registered in
the global TOOL_REGISTRY because session_id varies per request.
"""
import logging
from typing import Callable

from core.upstash import search_document_chunks

logger = logging.getLogger(__name__)


async def _embed_query(query: str) -> list[float]:
    """Embed a single query string using OpenAI text-embedding-3-small."""
    from openai import AsyncOpenAI
    from core.config import settings
    
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=[query],
    )
    return response.data[0].embedding


def make_search_document_handler(session_id: str) -> Callable:
    """
    Returns an async handler(query, top_k=5) pre-bound to session_id.
    Embeds the query, runs similarity search in Upstash, returns top chunks.
    """
    async def handler(query: str, top_k: int = 5) -> dict:
        logger.info(
            "[doc:search] session=%s query=%r top_k=%d",
            session_id, query[:80], top_k,
        )
        try:
            embedding = await _embed_query(query)
            results = await search_document_chunks(
                session_id=session_id,
                query_embedding=embedding,
                top_k=top_k,
            )
            if not results:
                return {"chunks": [], "message": "No relevant passages found in the uploaded document."}
            return {
                "chunks": [
                    {"text": r["text"], "score": r["score"], "filename": r["filename"]}
                    for r in results
                ]
            }
        except Exception as exc:
            logger.warning("[doc:search] failed session=%s: %s", session_id, exc)
            return {"error": str(exc), "chunks": []}

    return handler
