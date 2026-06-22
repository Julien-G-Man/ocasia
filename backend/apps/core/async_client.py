"""
Async HTTP Client for FastAPI Proxy Pattern

This module provides a persistent httpx.AsyncClient with connection pooling
for high-performance async proxying from Django to FastAPI.
"""
import asyncio
import os
import httpx
import logging
from urllib.parse import urlsplit
from django.conf import settings

logger = logging.getLogger(__name__)

# Global persistent client instances keyed by base URL.
# Stored as (client, loop_id) so we can detect stale clients whose event loop
# has been closed (common on the Windows dev server where asgiref creates a new
# loop per request).
_async_clients: dict[str, tuple[httpx.AsyncClient, int]] = {}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_base_url(url: str) -> str:
    base = (url or "").strip().rstrip("/")
    if not base:
        return ""
    if not base.startswith(("http://", "https://")):
        # Favor HTTPS for production hosts when scheme is omitted.
        base = f"https://{base}"
    parts = urlsplit(base)
    if not parts.netloc:
        return ""

    # Keep only scheme + host(+port). Path suffixes like "/api" break
    # call_fastapi("/chatbot/") by turning it into "/api/chatbot/".
    normalized = f"{parts.scheme}://{parts.netloc}".rstrip("/")
    if parts.path and parts.path not in ("", "/"):
        logger.warning(
            "FASTAPI base URL contains path '%s'; using origin '%s' instead",
            parts.path,
            normalized,
        )
    return normalized


def get_fastapi_base_urls() -> list[str]:
    """
    Resolve one or more FastAPI base URLs.
    Priority:
    1) FASTAPI_BASE_URLS (comma-separated)
    2) FASTAPI_BASE_URL
    """
    urls: list[str] = []
    raw_multi = getattr(settings, "FASTAPI_BASE_URLS", "")
    if raw_multi:
        for item in str(raw_multi).split(","):
            normalized = _normalize_base_url(item)
            if normalized:
                urls.append(normalized)

    if not urls:
        single = _normalize_base_url(getattr(settings, "FASTAPI_BASE_URL", "http://localhost:8001"))
        if single:
            urls.append(single)

    return list(dict.fromkeys(urls))


def _current_loop_id() -> int:
    """Return id() of the running event loop, or 0 if none is running."""
    try:
        return id(asyncio.get_event_loop())
    except RuntimeError:
        return 0


def _make_client(fastapi_base: str) -> httpx.AsyncClient:
    base_urls = get_fastapi_base_urls()
    timeout = httpx.Timeout(
        connect=_env_float("DJANGO_FASTAPI_CONNECT_TIMEOUT", 5.0),
        read=_env_float("DJANGO_FASTAPI_READ_TIMEOUT", 120.0),
        write=_env_float("DJANGO_FASTAPI_WRITE_TIMEOUT", 10.0),
        pool=_env_float("DJANGO_FASTAPI_POOL_TIMEOUT", 6.0),
    )
    client = httpx.AsyncClient(
        base_url=fastapi_base,
        timeout=timeout,
        limits=httpx.Limits(
            max_keepalive_connections=_env_int("DJANGO_FASTAPI_MAX_KEEPALIVE", 200),
            max_connections=_env_int("DJANGO_FASTAPI_MAX_CONNECTIONS", 1000),
            keepalive_expiry=30.0,
        ),
        http2=True,
    )
    logger.info("Initialized FastAPI AsyncClient. primary=%s all=%s", fastapi_base, base_urls)
    return client


def get_async_client(base_url: str | None = None) -> httpx.AsyncClient:
    """
    Get or create the persistent async HTTP client.

    Clients are keyed by (base_url, event_loop_id).  On the Windows dev server
    asgiref creates a new event loop per request, so the cached client would
    otherwise be tied to a dead loop.  When the loop changes we discard the
    stale entry (we cannot await aclose() because the old loop is already gone)
    and create a fresh client bound to the current loop.
    """
    global _async_clients
    fastapi_base = _normalize_base_url(base_url) if base_url else ""
    if not fastapi_base:
        urls = get_fastapi_base_urls()
        fastapi_base = urls[0] if urls else "http://localhost:8001"

    loop_id = _current_loop_id()

    if fastapi_base in _async_clients:
        cached_client, cached_loop_id = _async_clients[fastapi_base]
        if cached_loop_id == loop_id:
            return cached_client
        # Loop has changed — the cached client's transport is dead.
        # Discard silently; we cannot aclose() on a closed loop.
        logger.debug("Event loop changed, recreating AsyncClient for %s", fastapi_base)
        del _async_clients[fastapi_base]

    client = _make_client(fastapi_base)
    _async_clients[fastapi_base] = (client, loop_id)
    return client


async def close_async_client():
    """Close the async client (call during Django shutdown)"""
    global _async_clients
    if not _async_clients:
        return
    for base, (client, _loop_id) in list(_async_clients.items()):
        await client.aclose()
        logger.info("Closed persistent AsyncClient for %s", base)
    _async_clients = {}


def build_fastapi_headers() -> dict:
    """
    Build headers for FastAPI requests with authentication.
    
    Uses a secret header instead of forwarding full Django session
    for better security and performance.
    """
    fastapi_secret = getattr(settings, "FASTAPI_SECRET")
    return {
        "X-Internal-Secret": fastapi_secret,
        "Content-Type": "application/json",
    }


async def call_fastapi(
    method: str,
    path: str,
    *,
    retries_per_url: int = 2,
    retry_delay_seconds: float = 0.6,
    **kwargs,
) -> httpx.Response:
    """
    Call FastAPI with retry + URL failover.
    Raises httpx.RequestError if all attempts fail.
    """
    urls = get_fastapi_base_urls()
    if not urls:
        raise httpx.RequestError("No FASTAPI base URL configured")

    safe_path = path if path.startswith("/") else f"/{path}"

    last_error: Exception | None = None
    retry_status_codes = {404, 502, 503, 504}

    for base in urls:
        client = get_async_client(base)
        for attempt in range(1, retries_per_url + 1):
            try:
                logger.debug(
                    "FastAPI request method=%s base=%s path=%s attempt=%s/%s",
                    method,
                    base,
                    safe_path,
                    attempt,
                    retries_per_url,
                )
                response = await client.request(method=method, url=safe_path, **kwargs)

                # If one base URL is stale/misconfigured, fall through to next URL.
                if response.status_code in retry_status_codes and len(urls) > 1:
                    logger.warning(
                        "FastAPI endpoint failure base=%s path=%s status=%s; trying next base URL",
                        base,
                        safe_path,
                        response.status_code,
                    )
                    if attempt < retries_per_url:
                        await asyncio.sleep(retry_delay_seconds * attempt)
                        continue
                    break

                return response
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, httpx.RequestError) as exc:
                last_error = exc
                logger.warning(
                    "FastAPI request failed base=%s attempt=%s/%s path=%s error=%s",
                    base,
                    attempt,
                    retries_per_url,
                    safe_path,
                    exc,
                )
                if attempt < retries_per_url:
                    await asyncio.sleep(retry_delay_seconds * attempt)

    raise httpx.RequestError(
        f"All FastAPI connection attempts failed for path {safe_path}. urls={urls}. last_error={last_error}"
    )

