import logging
import os

import httpx

logger = logging.getLogger(__name__)


async def kb_search(query: str, top_k: int = 4) -> dict:
    """Search indexed Ocasia platform knowledge in the shared hybrid RAG corpus."""
    from apps.tutor.retrieval import rag_engine

    try:
        results = await rag_engine.search(
            query, top_k=max(1, min(int(top_k), 8)), source_type="platform_kb"
        )
        return {
            "chunks": results,
            "note": "No relevant platform knowledge found." if not results else "",
        }
    except Exception as exc:
        logger.exception("Platform knowledge retrieval failed")
        return {"chunks": [], "error": str(exc)}


async def search_web(query: str, num_results: int = 3) -> dict:
    """Search the public web for current information and return source snippets."""
    api_key = os.environ.get("SEARCH_API_KEY") or os.environ.get("TAVILY_API_KEY")
    if not api_key:
        logger.warning("SEARCH_API_KEY is not configured")
        return {"results": []}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": max(1, min(int(num_results), 5)),
                    "include_answer": False,
                    "include_raw_content": False,
                },
            )
            response.raise_for_status()
        return {
            "results": [
                {"title": row.get("title", ""), "url": row.get("url", ""), "snippet": row.get("content", "")}
                for row in response.json().get("results", [])
            ]
        }
    except Exception as exc:
        logger.warning("Web search failed for %r: %s", query[:80], exc)
        return {"results": []}
