"""
Upstash Vector client wrapper for document RAG.

Responsibilities:
- Embed text chunks via OpenAI text-embedding-3-small
- Upsert vectors into Upstash (namespaced by session_id)
- Query top-k similar chunks for a given query
- Delete a namespace (called on session cleanup if needed)

Each session gets its own namespace so vectors never bleed across users.
"""
import logging

from core.config import settings

logger = logging.getLogger(__name__)


def _get_async_index():
    """Return an Upstash AsyncIndex configured from settings."""
    try:
        from upstash_vector import AsyncIndex
    except ImportError:
        raise RuntimeError(
            "upstash-vector is not installed. Add it to requirements.txt and reinstall."
        )
    if not settings.UPSTASH_VECTOR_URL or not settings.UPSTASH_VECTOR_TOKEN:
        raise RuntimeError(
            "UPSTASH_VECTOR_URL and UPSTASH_VECTOR_TOKEN must be set for document RAG."
        )
    return AsyncIndex(
        url=settings.UPSTASH_VECTOR_URL,
        token=settings.UPSTASH_VECTOR_TOKEN,
    )


async def _embed_chunks(chunks: list[str]) -> list[list[float]]:
    """
    Embed a list of text chunks using OpenAI text-embedding-3-small.
    Returns a list of float vectors (one per chunk).
    """
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise RuntimeError("openai package is required for document embedding.")

    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY must be set for document embedding.")

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=chunks,
    )
    return [item.embedding for item in response.data]


async def upsert_document_chunks(
    session_id: str,
    chunks: list[str],
    filename: str = "",
) -> int:
    """
    Embed chunks and upsert them into Upstash Vector under the session namespace.
    Returns the number of vectors upserted.
    """
    if not chunks:
        return 0

    index = _get_async_index()
    vectors = await _embed_chunks(chunks)

    records = [
        {
            "id": f"{session_id}-{i}",
            "vector": vectors[i],
            "metadata": {
                "chunk_index": i,
                "text": chunks[i],
                "filename": filename,
                "session_id": session_id,
            },
        }
        for i in range(len(chunks))
    ]

    await index.upsert(vectors=records, namespace=session_id)
    logger.info(
        "[upstash] upserted %d vectors session=%s file=%s",
        len(records), session_id, filename,
    )
    return len(records)


async def search_document_chunks(
    session_id: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """
    Query Upstash Vector for the top-k most similar chunks in the session namespace.
    Returns list of dicts: {text, score, chunk_index, filename}
    """
    index = _get_async_index()
    results = await index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True,
        namespace=session_id,
    )

    return [
        {
            "text": r.metadata.get("text", "") if r.metadata else "",
            "score": round(r.score, 4),
            "chunk_index": r.metadata.get("chunk_index", 0) if r.metadata else 0,
            "filename": r.metadata.get("filename", "") if r.metadata else "",
        }
        for r in results
    ]


async def delete_session_namespace(session_id: str) -> None:
    """Delete all vectors for a session namespace (call on session cleanup)."""
    try:
        index = _get_async_index()
        await index.delete_namespace(session_id)
        logger.info("[upstash] deleted namespace session=%s", session_id)
    except Exception as exc:
        logger.warning("[upstash] failed to delete namespace %s: %s", session_id, exc)
