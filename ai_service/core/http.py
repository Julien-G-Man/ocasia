import httpx
from core.config import settings

async_client: httpx.AsyncClient | None = None


async def get_async_client():
    global async_client
    if async_client is None:
        async_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=settings.FASTAPI_OUTBOUND_CONNECT_TIMEOUT,
                read=settings.FASTAPI_OUTBOUND_READ_TIMEOUT,
                write=settings.FASTAPI_OUTBOUND_WRITE_TIMEOUT,
                pool=settings.FASTAPI_OUTBOUND_POOL_TIMEOUT,
            ),
            limits=httpx.Limits(
                max_connections=settings.FASTAPI_OUTBOUND_MAX_CONNECTIONS,
                max_keepalive_connections=settings.FASTAPI_OUTBOUND_MAX_KEEPALIVE,
                keepalive_expiry=30,
            ),
            http2=False,
        )
    return async_client
