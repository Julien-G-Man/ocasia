"""
MCP Tool: search_web

Calls the Tavily Search API to retrieve current web results.
Used by the AI when a question requires up-to-date or factual
information that is not in the platform knowledge base.
"""

import logging
import os

logger = logging.getLogger(__name__)


async def search_web(query: str, num_results: int = 3) -> dict:
    """
    Returns:
        {"results": [{"title": str, "url": str, "snippet": str}]}

    Falls back to an empty list if the API key is missing or the call fails.
    """
    api_key = os.environ.get("SEARCH_API_KEY") or os.environ.get("TAVILY_API_KEY")
    if not api_key:
        logger.warning("[mcp:search] SEARCH_API_KEY not set — returning empty results")
        return {"results": []}

    try:
        import httpx
        num_results = max(1, min(int(num_results), 5))

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": num_results,
                    "include_answer": False,
                    "include_raw_content": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            }
            for r in data.get("results", [])
        ]
        logger.debug("[mcp:search] query=%r results=%d", query[:80], len(results))
        return {"results": results}

    except Exception as exc:
        logger.warning("[mcp:search] search failed for %r: %s", query[:80], exc)
        return {"results": []}
