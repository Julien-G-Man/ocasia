"""
High-Performance Async Proxy Views for Chatbot

These views implement the Asynchronous Proxy Pattern for chatbot endpoints:
- Django handles session/auth and DB operations (fast)
- Proxies LLM requests to FastAPI with async streaming
- Zero-copy streaming for optimal performance
"""
import json
import logging
from time import perf_counter
import httpx
from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from asgiref.sync import sync_to_async
from .file_extractor import extract_text_from_file, FileExtractionError
from apps.core.async_client import call_fastapi, build_fastapi_headers
from .helpers import (
    _resolve_authenticated_user,
    _get_or_create_session,
    _save_user_message,
    _save_ai_message,
    _get_conversation_history,
    _build_chatbot_prompt,
    _build_mcp_context,
    fallback_response,
)
from .models import ChatSession

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
async def chatbot_api_async(request):
    """
    High-performance async proxy for chatbot API endpoint.
    
    Flow:
    1. Django handles session/auth (fast)
    2. Saves user message to DB
    3. Builds prompt with conversation history
    4. Proxies to FastAPI with async client
    5. Saves AI response to DB
    6. Returns response
    """
    try:
        # Parse request
        data = json.loads(request.body) if request.body else {}
        user_message = data.get('message', '')
        session_id = data.get('session_id', None)  # Get session_id from request

        if not user_message:
            return JsonResponse({"error": "Message is required"}, status=400)

        # 1. Django handles session/auth (fast DB operations)
        user, session_obj = await _get_or_create_session(request, session_id=session_id)
        
        # 2. Save user message
        await _save_user_message(session_obj, user_message)
        
        # 3. Get conversation history (last 10 conversations = 20 messages)
        conversation_history = await _get_conversation_history(session_obj, limit=20)
        
        max_tokens = getattr(settings, "CHATBOT_MAX_TOKENS", 1200)
        use_mcp = getattr(settings, "CHATBOT_USE_MCP", False)

        # 4 & 5. Build prompt / messages, forward to FastAPI
        try:
            headers = build_fastapi_headers()

            if use_mcp:
                # ── MCP path: AI-driven tool loop ──────────────────────────
                # Build system prompt + Anthropic messages list separately
                system_prompt, messages = await _build_mcp_context(
                    user_message, conversation_history, user=user
                )
                # Restrict to chatbot-appropriate tools (no quiz/flashcard page tools)
                mcp_tools = getattr(
                    settings,
                    "CHATBOT_MCP_TOOLS",
                    None,  # None = all registered tools
                )
                logger.info(
                    "[chatbot:mcp] orchestrate start session=%s tools=%s",
                    getattr(session_obj, "session_id", "?"), mcp_tools,
                )
                fastapi_resp = await call_fastapi(
                    "POST",
                    "/mcp/orchestrate",
                    json={
                        "messages": messages,
                        "system_prompt": system_prompt,
                        "tools": mcp_tools,
                        "max_tokens": max_tokens,
                        "max_iterations": getattr(settings, "CHATBOT_MCP_MAX_ITERATIONS", 5),
                    },
                    headers=headers,
                    timeout=120.0,  # tool loops take longer than single-shot calls
                )

                if fastapi_resp.status_code != 200:
                    logger.warning(
                        "[chatbot:mcp] orchestrate returned %d: %s",
                        fastapi_resp.status_code, fastapi_resp.text[:200],
                    )
                    # Fall through to one-shot fallback below
                    use_mcp = False

                if use_mcp:
                    try:
                        resp_json = fastapi_resp.json()
                        ai_response = resp_json.get("response", "")
                        tool_calls_made = resp_json.get("tool_calls_made", [])
                        iterations = resp_json.get("iterations", 0)
                        mcp_error = resp_json.get("error")

                        if mcp_error:
                            logger.warning(
                                "[chatbot:mcp] orchestrate error: %s (calls=%s iter=%d)",
                                mcp_error, tool_calls_made, iterations,
                            )

                        logger.info(
                            "[chatbot:mcp] done session=%s calls=%s iter=%d response_len=%d",
                            getattr(session_obj, "session_id", "?"),
                            tool_calls_made, iterations, len(ai_response),
                        )

                        if not ai_response:
                            logger.warning("[chatbot:mcp] empty response — falling back to one-shot")
                            use_mcp = False  # fall through to one-shot below
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        logger.error("[chatbot:mcp] failed to parse orchestrate response: %s", e)
                        use_mcp = False

            if not use_mcp:
                # ── Original one-shot path (fallback or default) ───────────
                full_prompt = await _build_chatbot_prompt(user_message, conversation_history, user=user)
                fastapi_resp = await call_fastapi(
                    "POST",
                    "/chatbot/",
                    json={"prompt": full_prompt, "max_tokens": max_tokens},
                    headers=headers,
                    timeout=60.0,
                )

                if fastapi_resp.status_code != 200:
                    logger.warning(
                        "[chatbot] FastAPI responded %d: %s",
                        fastapi_resp.status_code, fastapi_resp.text[:200],
                    )
                    return JsonResponse({"error": "AI service temporarily unavailable"}, status=503)

                try:
                    resp_json = fastapi_resp.json()
                    ai_response = resp_json.get("response", "")

                    # Azure format fallback
                    if not ai_response and "choices" in resp_json:
                        choices = resp_json.get("choices", [])
                        if choices:
                            choice = choices[0]
                            if isinstance(choice, dict):
                                message = choice.get("message", {})
                                if isinstance(message, dict):
                                    ai_response = message.get("content", "")

                    if not ai_response:
                        logger.warning("[chatbot] empty response from FastAPI: %s", resp_json)
                        ai_response = fallback_response(user_message)
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.error("[chatbot] failed to parse FastAPI response: %s", e)
                    ai_response = fallback_response(user_message)

        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logger.error(
                    "Event loop is closed. Django must run with ASGI (uvicorn/daphne), not WSGI."
                )
                return JsonResponse(
                    {"error": "Server configuration error. Please contact administrator."},
                    status=500,
                )
            raise
        
        # Clean markdown
        cleaned_response = ai_response.strip()
        
        # 6. Save AI message
        try:
            await _save_ai_message(session_obj, cleaned_response)
        except Exception as e:
            logger.error(f"Failed to save AI response: {e}", exc_info=True)
            return JsonResponse({"error": "Failed to save response"}, status=500)
        
        return JsonResponse({"response": cleaned_response, "session_id": session_obj.session_id})
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except httpx.TimeoutException:
        logger.error("FastAPI request timed out")
        return JsonResponse({"error": "Request timeout"}, status=504)
    except httpx.RequestError as e:
        logger.error(f"FastAPI request error: {e}")
        return JsonResponse({"error": "Service unavailable"}, status=503)
    except RuntimeError as e:
        if "Event loop is closed" in str(e) or "cannot be called from a running event loop" in str(e):
            logger.error("Event loop error. Django must run with ASGI server (uvicorn/daphne), not WSGI (runserver).")
            return JsonResponse(
                {"error": "Server configuration error. Please ensure Django is running with uvicorn."}, 
                status=500
            )
        raise
    except Exception as e:
        logger.error(f"Chatbot API error: {e}", exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
async def chatbot_file_api_async(request):
    """
    Async proxy for file uploads. 
    Extracts text in Django, then proxies the prompt to FastAPI with full context.
    """
    session_obj = None

    try:
        if 'file_upload' not in request.FILES:
            return JsonResponse({'error': 'No file uploaded.'}, status=400)
        
        file = request.FILES['file_upload']
        # For multipart/form-data, data is in request.POST
        user_message = request.POST.get('message', 'Analyze the uploaded document.')
        session_id = request.POST.get('session_id', None)
        filename = file.name

        logger.info(f"Processing file upload: {filename}, message: {user_message[:50]}")

        # 1. Extract text (Keep this sync_to_async as file reading is blocking)
        try:
            context_document = await sync_to_async(extract_text_from_file)(file)
            logger.debug(f"Extracted {len(context_document)} characters from {filename}")
        except FileExtractionError as fee:
            logger.warning(f"File extraction error: {fee}")
            return JsonResponse({"error": str(fee)}, status=400)

        # 2. Session & History
        user, session_obj = await _get_or_create_session(request, session_id=session_id)
        if session_obj is None:
            # Auth token absent or invalid — reject before wasting AI compute
            logger.warning("File upload rejected: unauthenticated request (no valid token)")
            return JsonResponse({"error": "Authentication required for file uploads."}, status=401)
        logger.debug("Authenticated session in use: %s", getattr(session_obj, "id", None))
        
        # 3. Save user message with file reference
        display_message = f"{user_message} (File: {filename})"
        await _save_user_message(session_obj, display_message)
        
        # 4. Get History & Build Prompt with FILE CONTEXT
        history = await _get_conversation_history(session_obj)
        full_prompt = await _build_chatbot_prompt(user_message, history, context_document=context_document, user=user)
        
        logger.debug(f"Built prompt with {len(context_document)} chars of file context for {filename}")

        # 5. Proxy to FastAPI
        headers = build_fastapi_headers()
        
        # Note: Ensure the slash matches your FastAPI route exactly to avoid 307 redirects
        try:
            fastapi_resp = await call_fastapi(
                "POST",
                "/chatbot/",
                json={"prompt": full_prompt, "max_tokens": 2000},  # document analysis needs more output tokens
                headers=headers,
                timeout=120.0, # Files take longer to process
            )
        except httpx.TimeoutException:
            logger.error(f"FastAPI request timed out for file {filename}")
            return JsonResponse({"error": "Request timed out processing file"}, status=504)
        except httpx.RequestError as e:
            logger.error(f"FastAPI request error: {e}")
            return JsonResponse({"error": "Service temporarily unavailable"}, status=503)

        if fastapi_resp.status_code != 200:
            logger.error(f"FastAPI Error {fastapi_resp.status_code}: {fastapi_resp.text}")
            return JsonResponse(
                {"error": "AI provider rejected the content. Try a different file or message."}, 
                status=503
            )

        # Parse response
        try:
            resp_json = fastapi_resp.json()
            ai_response = resp_json.get("response", "")
            
            # Try to extract from Azure format if needed
            if not ai_response and "choices" in resp_json:
                choices = resp_json.get("choices", [])
                if choices and len(choices) > 0:
                    choice = choices[0]
                    if isinstance(choice, dict):
                        message = choice.get("message", {})
                        if isinstance(message, dict):
                            ai_response = message.get("content", "")
            
            # If still no response, it might be a string response (e.g., Azure safety block)
            if not ai_response:
                # Check if response itself is a string (safety block or other message)
                if isinstance(resp_json, str):
                    ai_response = resp_json
                else:
                    logger.warning(f"FastAPI returned empty response for file {filename}. Response: {resp_json}")
                    ai_response = "I processed the file but received an empty response. Please try again."
                
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to parse FastAPI response: {e}. Response text: {fastapi_resp.text[:200]}")
            ai_response = "Failed to parse AI response. Please try again."

        # 6. Clean and Save
        cleaned_response = ai_response.strip()
        await _save_ai_message(session_obj, cleaned_response)
        
        logger.info(f"Successfully processed file {filename} with {len(cleaned_response)} char response")

        return JsonResponse({
            "response": cleaned_response,
            "session_id": getattr(session_obj, "session_id", session_id),
            "filename": file.name
        })

    except Exception as e:
        logger.error(f"Async File API Error: {e}", exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
async def chatbot_stream_async(request):
    """
    High-performance async streaming proxy for chatbot endpoint.
    
    Streams LLM response chunks directly from FastAPI to client with zero-copy.
    """
    try:
        # Parse request
        data = json.loads(request.body) if request.body else {}
        user_message = data.get('message', '')
        session_id = data.get('session_id', None)

        if not user_message:
            return JsonResponse({"error": "Message is required"}, status=400)

        # 1. Django handles session/auth
        user, session_obj = await _get_or_create_session(request, session_id=session_id)
        
        # 2. Save user message
        await _save_user_message(session_obj, user_message)
        
        # 3. Get conversation history (last 10 conversations = 20 messages)
        conversation_history = await _get_conversation_history(session_obj, limit=20)
        
        # 4. Build full prompt
        full_prompt = await _build_chatbot_prompt(user_message, conversation_history, user=user)
        max_tokens = getattr(settings, "CHATBOT_MAX_TOKENS", 1200)
        
        # 5. Forward to FastAPI (Note: FastAPI doesn't stream yet, so we get full response and stream it)
        try:
            headers = build_fastapi_headers()
            fastapi_resp = await call_fastapi(
                "POST",
                "/chatbot/",
                json={"prompt": full_prompt, "max_tokens": max_tokens},
                headers=headers,
                timeout=60.0,
            )
            
            if fastapi_resp.status_code != 200:
                logger.warning(f"FastAPI responded {fastapi_resp.status_code}: {fastapi_resp.text}")
                return JsonResponse(
                    {"error": "AI service temporarily unavailable"}, 
                    status=503
                )
            
            # Parse response
            try:
                resp_json = fastapi_resp.json()
                ai_response = resp_json.get("response", "")
                
                # If response is empty or None, try to extract from choices (Azure format)
                if not ai_response and "choices" in resp_json:
                    choices = resp_json.get("choices", [])
                    if choices and len(choices) > 0:
                        choice = choices[0]
                        if isinstance(choice, dict):
                            message = choice.get("message", {})
                            if isinstance(message, dict):
                                ai_response = message.get("content", "")
                
                # If still no response, it might be a string response (e.g., Azure safety block)
                if not ai_response:
                    if isinstance(resp_json, str):
                        ai_response = resp_json
                    else:
                        logger.warning(f"FastAPI returned empty response. Full response: {resp_json}")
                        ai_response = fallback_response(user_message)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.error(f"Failed to parse FastAPI response: {e}. Response text: {fastapi_resp.text[:200]}")
                ai_response = fallback_response(user_message)
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logger.error("Event loop is closed. Django must run with ASGI server (uvicorn/daphne), not WSGI (runserver).")
                return JsonResponse(
                    {"error": "Server configuration error. Please contact administrator."}, 
                    status=500
                )
            raise
        
        # Clean markdown
        cleaned_response = ai_response.strip()
        
        # Stream the response in chunks to simulate streaming
        async def stream_generator():
            # Stream in chunks of ~10 characters for smooth UX
            chunk_size = 10
            for i in range(0, len(cleaned_response), chunk_size):
                chunk = cleaned_response[i:i+chunk_size]
                yield chunk.encode('utf-8')
                # Small delay to simulate streaming (optional, can be removed)
                import asyncio
                await asyncio.sleep(0.01)
            
            # Save to DB after streaming completes
            try:
                await _save_ai_message(session_obj, cleaned_response)
                logger.debug("Saved streamed response. session=%s", getattr(session_obj, "id", None))
            except Exception as e:
                logger.error(f"Failed to save streamed response to DB: {e}", exc_info=True)
        
        # Create streaming response
        return StreamingHttpResponse(
            stream_generator(),
            content_type="text/plain; charset=utf-8"
        )
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except httpx.TimeoutException:
        logger.error("FastAPI request timed out")
        return JsonResponse({"error": "Request timeout"}, status=504)
    except httpx.RequestError as e:
        logger.error(f"FastAPI request error: {e}")
        return JsonResponse({"error": "Service unavailable"}, status=503)
    except RuntimeError as e:
        if "Event loop is closed" in str(e) or "cannot be called from a running event loop" in str(e):
            logger.error("Event loop error. Django must run with ASGI server (uvicorn/daphne), not WSGI (runserver).")
            return JsonResponse(
                {"error": "Server configuration error. Please ensure Django is running with uvicorn."}, 
                status=500
            )
        raise
    except Exception as e:
        logger.error(f"Chatbot Stream API error: {e}", exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)


@require_http_methods(["GET"])
async def get_conversation_history(request):
    """
    Diagnostic endpoint to retrieve conversation history for current session.
    Useful for debugging and verifying messages are being saved correctly.
    
    Returns: List of all messages in the current user's session.
    """
    start = perf_counter()
    try:
        requested_session_id = request.GET.get("session_id")

        if requested_session_id:
            user = await _resolve_authenticated_user(request)
            if not user:
                return JsonResponse({"detail": "Authentication required"}, status=401)

            session_obj = await sync_to_async(
                ChatSession.objects.filter(
                    user=user,
                    session_id=requested_session_id,
                ).first
            )()

            if not session_obj:
                return JsonResponse({"detail": "Session not found"}, status=404)
        else:
            user, session_obj = await _get_or_create_session(request)

        if not user or not session_obj:
            return JsonResponse({"detail": "Authentication required"}, status=401)
        
        # Get ALL messages (not just last 10)
        all_messages = await sync_to_async(list)(
            session_obj.messages.all().order_by('created_at')
        )
        
        messages_data = []
        for msg in all_messages:
            messages_data.append({
                "id": msg.id,
                "sender": msg.sender,
                "content": msg.content,
                "created_at": msg.created_at.isoformat()
            })
        
        return JsonResponse({
            "session_id": session_obj.session_id,
            "user": str(user) if user else None,
            "user_id": getattr(user, "id", None),
            "message_count": len(messages_data),
            "messages": messages_data
        })
    except Exception as e:
        logger.error(f"Get conversation history error: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)
    finally:
        duration_ms = (perf_counter() - start) * 1000
        logger.info(
            "[chatbot] get_history session=%s duration_ms=%.2f",
            request.GET.get("session_id", "(auto)"),
            duration_ms,
        )


@require_http_methods(["DELETE"])
async def clear_conversation_history(request):
    """
    Delete conversation history for the current session or a specific session_id.
    """
    start = perf_counter()
    try:
        requested_session_id = request.GET.get("session_id")

        if requested_session_id:
            user = await _resolve_authenticated_user(request)
            if not user:
                return JsonResponse({"detail": "Authentication required"}, status=401)

            session_obj = await sync_to_async(
                ChatSession.objects.filter(
                    user=user,
                    session_id=requested_session_id,
                ).first
            )()
        else:
            user, session_obj = await _get_or_create_session(request)

        if not user or not session_obj:
            return JsonResponse({"detail": "Authentication required"}, status=401)
        deleted_count, _ = await sync_to_async(session_obj.delete, thread_sensitive=True)()
        
        logger.info("Deleted chat session %s for user %s", session_obj.session_id, getattr(user, "id", None))
        
        return JsonResponse({
            "status": "success",
            "deleted_count": deleted_count,
            "session_id": session_obj.session_id
        })
    except Exception as e:
        logger.error(f"Clear conversation history error: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)
    finally:
        duration_ms = (perf_counter() - start) * 1000
        logger.info("[chatbot] clear_history duration_ms=%.2f", duration_ms)


@csrf_exempt
@require_http_methods(["POST", "PATCH"])
async def rename_conversation_session(request):
    """Rename a chat session for the authenticated user."""
    start = perf_counter()
    try:
        data = json.loads(request.body) if request.body else {}
        requested_session_id = data.get("session_id") or request.GET.get("session_id")
        new_title = (data.get("title") or data.get("name") or "").strip()

        if not requested_session_id:
            return JsonResponse({"detail": "session_id is required"}, status=400)
        if not new_title:
            return JsonResponse({"detail": "title is required"}, status=400)

        user = await _resolve_authenticated_user(request)
        if not user:
            return JsonResponse({"detail": "Authentication required"}, status=401)

        session_obj = await sync_to_async(
            ChatSession.objects.filter(
                user=user,
                session_id=requested_session_id,
            ).first
        )()

        if not session_obj:
            return JsonResponse({"detail": "Session not found"}, status=404)

        session_obj.title = new_title[:120]
        await sync_to_async(session_obj.save, thread_sensitive=True)(update_fields=["title"])

        return JsonResponse({
            "status": "success",
            "session_id": session_obj.session_id,
            "title": session_obj.title,
        })
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"Rename conversation session error: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)
    finally:
        duration_ms = (perf_counter() - start) * 1000
        logger.info("[chatbot] rename_session duration_ms=%.2f", duration_ms)
