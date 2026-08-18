"""
High-Performance Async Proxy Views for FastAPI

These views implement the Asynchronous Proxy Pattern:
- Django handles auth/session checks (fast, synchronous DB operations)
- Then proxies I/O-heavy LLM requests to FastAPI using async streaming
- Zero-copy streaming ensures minimal memory overhead
"""
import json
import logging
from typing import Optional
from django.conf import settings
from django.http import (
    HttpResponse, 
    StreamingHttpResponse, 
    JsonResponse,
    HttpRequest
)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
import httpx

from .async_client import get_async_client, build_fastapi_headers

logger = logging.getLogger(__name__)


async def _forward_to_fastapi(
    request: HttpRequest,
    fastapi_path: str,
    method: str = "POST",
    json_data: Optional[dict] = None,
    stream: bool = False,
    timeout: Optional[float] = None
) -> httpx.Response:
    """
    Forward a request to FastAPI with proper authentication headers.
    
    Args:
        request: Django request object
        fastapi_path: Path on FastAPI service (e.g., "/chatbot")
        method: HTTP method (default: POST)
        json_data: JSON payload to send
        stream: Whether to stream the response
        timeout: Optional timeout override
        
    Returns:
        httpx.Response object
    """
    client = get_async_client()
    headers = build_fastapi_headers()
    
    # Forward relevant headers from original request
    if "Content-Type" in request.headers:
        headers["Content-Type"] = request.headers["Content-Type"]
    
    # Build the request
    fastapi_req = client.build_request(
        method=method,
        url=fastapi_path,
        json=json_data,
        headers=headers,
    )
    
    # Send with streaming if requested
    if stream:
        return await client.send(fastapi_req, stream=True)
    else:
        return await client.send(fastapi_req)


@csrf_exempt
@require_http_methods(["POST"])
async def llm_proxy_view(request: HttpRequest):
    """
    High-performance async proxy for LLM endpoints.
    
    This view:
    1. Handles Django auth/session checks (fast, synchronous)
    2. Forwards request to FastAPI using async client
    3. Streams response back to client with zero-copy
    
    Usage: Configure this for endpoints that need to proxy to FastAPI
    """
    # 1. Django handles Auth/Business logic (Fast)
    if not request.user.is_authenticated:
        # Allow anonymous users 
        # For stricter auth, uncomment:
        # return HttpResponse("Unauthorized", status=401)
        pass
    
    try:
        # Parse request body
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        
        # 2. Forward to FastAPI using Async Client with streaming
        fastapi_resp = await _forward_to_fastapi(
            request=request,
            fastapi_path="/chatbot/",
            json_data={
                "prompt": data.get("prompt", ""),
                "max_tokens": data.get("max_tokens", getattr(settings, "CHATBOT_MAX_TOKENS", 1200)),
            },
            stream=True  # Enable streaming for LLM responses
        )
        
        # 3. Stream the response directly back to client (zero-copy)
        return StreamingHttpResponse(
            fastapi_resp.aiter_bytes(),
            status=fastapi_resp.status_code,
            content_type=fastapi_resp.headers.get("Content-Type", "application/json")
        )
        
    except httpx.TimeoutException:
        logger.error("FastAPI request timed out")
        return JsonResponse({"error": "Request timeout"}, status=504)
    except httpx.RequestError as e:
        logger.error(f"FastAPI request error: {e}")
        return JsonResponse({"error": "Service unavailable"}, status=503)
    except Exception as e:
        logger.error(f"Unexpected error in proxy view: {e}", exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)

