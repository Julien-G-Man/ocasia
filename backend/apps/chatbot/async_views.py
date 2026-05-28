"""
Chatbot async proxy views.

Django responsibilities: auth, session management, message persistence, user stats, file extraction.
FastAPI responsibilities: all AI work (agent loop, KB search, web search, prompt construction).
"""
import json
import logging
from time import perf_counter

import httpx
from asgiref.sync import sync_to_async
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.core.async_client import call_fastapi, build_fastapi_headers


async def _record_ai_latency(feature: str, duration_ms: int) -> None:
    """Fire-and-forget: persist one AI response latency record."""
    try:
        from apps.dashboard.models import AIResponseLatency
        await sync_to_async(AIResponseLatency.objects.create)(
            feature=feature, duration_ms=duration_ms
        )
    except Exception:
        pass
from .file_extractor import extract_text_from_file, FileExtractionError
from .helpers import (
    _resolve_authenticated_user,
    _get_or_create_session,
    _save_user_message,
    _save_ai_message,
    _get_conversation_history,
    _fetch_user_performance_sync,
    fallback_response,
)
from .models import ChatSession

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
async def chatbot_api_async(request):
    try:
        data = json.loads(request.body) if request.body else {}
        user_message = data.get("message", "")
        session_id = data.get("session_id", None)
        tutor_mode = data.get("tutor_mode", "direct")

        if not user_message:
            return JsonResponse({"error": "Message is required"}, status=400)

        # 1. Auth + session
        user, session_obj = await _get_or_create_session(request, session_id=session_id)

        # 2. Save user message
        await _save_user_message(session_obj, user_message)

        # 3. Conversation history
        conversation_history = await _get_conversation_history(session_obj, limit=20)

        # 4. User stats (compact DB snapshot, ~60 tokens)
        user_stats = None
        if user:
            user_stats = await sync_to_async(_fetch_user_performance_sync, thread_sensitive=True)(user)

        # 5. Forward to FastAPI /agent/chat
        ai_response = ""
        chat_action = None
        chat_prefill = None
        try:
            headers = build_fastapi_headers()
            _t0 = perf_counter()
            fastapi_resp = await call_fastapi(
                "POST",
                "/agent/chat",
                json={
                    "message": user_message,
                    "conversation_history": conversation_history,
                    "tutor_mode": tutor_mode,
                    "user_stats": user_stats,
                    "user_id": getattr(user, "id", None),
                },
                headers=headers,
                timeout=120.0,
            )
            _chat_ms = int((perf_counter() - _t0) * 1000)
            import asyncio as _aio
            _aio.create_task(_record_ai_latency('chat', _chat_ms))

            if fastapi_resp.status_code == 200:
                resp_json = fastapi_resp.json()
                ai_response = resp_json.get("response", "")
                chat_action = resp_json.get("action")
                chat_prefill = resp_json.get("prefill")
                if not ai_response:
                    logger.warning("[chatbot] FastAPI returned empty response")
            else:
                chat_action = None
                chat_prefill = None
                logger.warning(
                    "[chatbot] FastAPI /agent/chat returned %d: %s",
                    fastapi_resp.status_code, fastapi_resp.text[:200],
                )

        except (httpx.TimeoutException, httpx.RequestError) as e:
            # Layer 3: FastAPI unreachable — static fallback, do not persist
            logger.error("[chatbot] FastAPI unreachable: %s", e)
            return JsonResponse(
                {"error": "AI service temporarily unavailable. Please try again shortly."},
                status=503,
            )

        if not ai_response:
            chat_action = None
            chat_prefill = None
            ai_response = fallback_response(user_message)

        # 6. Save + return
        cleaned = ai_response.strip()
        await _save_ai_message(session_obj, cleaned)
        response_payload = {
            "response": cleaned,
            "session_id": session_obj.session_id if session_obj else None,
        }
        if chat_action:
            response_payload["action"] = chat_action
        if chat_prefill:
            response_payload["prefill"] = chat_prefill
        return JsonResponse(response_payload)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error("[chatbot] chatbot_api_async error: %s", e, exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
async def chatbot_file_api_async(request):
    try:
        if "file_upload" not in request.FILES:
            return JsonResponse({"error": "No file uploaded."}, status=400)

        file = request.FILES["file_upload"]
        user_message = request.POST.get("message", "Analyze the uploaded document.")
        session_id = request.POST.get("session_id", None)
        tutor_mode = request.POST.get("tutor_mode", "direct")
        filename = file.name

        # Extract text in Django (keeps file handling out of FastAPI)
        try:
            file_text = await sync_to_async(extract_text_from_file)(file)
        except FileExtractionError as e:
            logger.warning("[chatbot:file] extraction error: %s", e)
            return JsonResponse({"error": str(e)}, status=400)

        # Auth + session (file uploads require authentication)
        user, session_obj = await _get_or_create_session(request, session_id=session_id)
        if session_obj is None:
            return JsonResponse({"error": "Authentication required for file uploads."}, status=401)

        # Save user message with file reference
        await _save_user_message(session_obj, f"{user_message} (File: {filename})")

        # History + stats
        history = await _get_conversation_history(session_obj)
        user_stats = (
            await sync_to_async(_fetch_user_performance_sync, thread_sensitive=True)(user)
            if user else None
        )

        # Forward to FastAPI
        try:
            headers = build_fastapi_headers()
            fastapi_resp = await call_fastapi(
                "POST",
                "/agent/chat",
                json={
                    "message": user_message,
                    "conversation_history": history,
                    "tutor_mode": tutor_mode,
                    "user_stats": user_stats,
                    "file_text": file_text,
                    "user_id": getattr(user, "id", None),
                },
                headers=headers,
                timeout=120.0,
            )
        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.error("[chatbot:file] FastAPI unreachable: %s", e)
            return JsonResponse({"error": "Service temporarily unavailable."}, status=503)

        if fastapi_resp.status_code != 200:
            logger.error(
                "[chatbot:file] FastAPI error %d for file %s",
                fastapi_resp.status_code, filename,
            )
            return JsonResponse(
                {"error": "AI provider rejected the content. Try a different file or message."},
                status=503,
            )

        resp_json = fastapi_resp.json()
        ai_response = resp_json.get("response", "") or "I processed the file but received an empty response."

        cleaned = ai_response.strip()
        await _save_ai_message(session_obj, cleaned)

        return JsonResponse({
            "response": cleaned,
            "session_id": getattr(session_obj, "session_id", session_id),
            "filename": filename,
        })

    except Exception as e:
        logger.error("[chatbot:file] error: %s", e, exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
async def create_quiz_from_agent(request):
    """
    Authenticated proxy: fetches user_stats then forwards to FastAPI /agent/quiz/generate/.
    Called by the inline quiz-param card in the chatbot UI.
    """
    try:
        data = json.loads(request.body) if request.body else {}
        topic = data.get("topic", "").strip()
        session_id = data.get("session_id", "").strip()
        if not topic:
            return JsonResponse({"error": "topic is required"}, status=400)

        user = await _resolve_authenticated_user(request)
        if not user:
            return JsonResponse({"error": "Authentication required"}, status=401)

        user_stats = await sync_to_async(_fetch_user_performance_sync, thread_sensitive=True)(user)

        try:
            headers = build_fastapi_headers()
            fastapi_resp = await call_fastapi(
                "POST",
                "/agent/quiz/generate/",
                json={
                    "topic": topic,
                    "num_questions": int(data.get("num_questions", 10)),
                    "time_limit": int(data.get("time_limit", 15)),
                    "user_stats": user_stats,
                },
                headers=headers,
                timeout=120.0,
            )
        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.error("[quiz/agent] FastAPI unreachable: %s", e)
            return JsonResponse({"error": "AI service temporarily unavailable."}, status=503)

        if fastapi_resp.status_code != 200:
            logger.error("[quiz/agent] FastAPI error %d: %s", fastapi_resp.status_code, fastapi_resp.text[:200])
            return JsonResponse({"error": "Quiz generation failed."}, status=503)

        resp_data = fastapi_resp.json()

        # Persist quiz as a special chat message so it survives session reloads across browsers.
        # The frontend detects the __QUIZ__: prefix in toUiMessage and renders a StartQuizCard.
        quiz_data = resp_data.get("quiz_data")
        if session_id and quiz_data:
            session_obj = await sync_to_async(
                ChatSession.objects.filter(user=user, session_id=session_id).first
            )()
            if session_obj:
                await _save_ai_message(session_obj, f"__QUIZ__:{json.dumps(quiz_data)}")

        return JsonResponse(resp_data)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error("[quiz/agent] error: %s", e, exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
async def chatbot_stream_api_async(request):
    """
    SSE streaming proxy for the chatbot.

    Connects to FastAPI POST /agent/chat/stream and forwards typed events
    (tool_start, tool_done, token, done, error) directly to the browser.
    Prepends a "session" event so the client knows the real session_id.
    Buffers all "token" content and saves the full AI response to the DB
    when the "done" event arrives.
    """
    try:
        data = json.loads(request.body) if request.body else {}
        user_message = data.get("message", "")
        session_id = data.get("session_id", None)
        tutor_mode = data.get("tutor_mode", "direct")

        if not user_message:
            return JsonResponse({"error": "Message is required"}, status=400)

        # Pre-flight: auth, session, history, stats (same as non-streaming view)
        user, session_obj = await _get_or_create_session(request, session_id=session_id)
        await _save_user_message(session_obj, user_message)
        conversation_history = await _get_conversation_history(session_obj, limit=20)

        user_stats = None
        if user:
            user_stats = await sync_to_async(_fetch_user_performance_sync, thread_sensitive=True)(user)

        real_session_id = session_obj.session_id if session_obj else session_id

        async def sse_generator():
            full_text_parts: list[str] = []

            # Tell the client the real (backend-assigned) session_id immediately
            yield f"data: {json.dumps({'type': 'session', 'session_id': real_session_id})}\n\n"

            try:
                from apps.core.async_client import build_fastapi_headers, get_fastapi_base_urls
                headers = build_fastapi_headers()
                base_urls = get_fastapi_base_urls()
                if not base_urls:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'AI service not configured.'})}\n\n"
                    return
                fastapi_base = base_urls[0]
                payload = {
                    "message": user_message,
                    "conversation_history": conversation_history,
                    "tutor_mode": tutor_mode,
                    "user_stats": user_stats,
                    "user_id": getattr(user, "id", None),
                }

                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream(
                        "POST",
                        f"{fastapi_base}/agent/chat/stream",
                        headers=headers,
                        json=payload,
                    ) as response:
                        if response.status_code != 200:
                            logger.error(
                                "[chatbot:stream] FastAPI returned %d", response.status_code
                            )
                            yield f"data: {json.dumps({'type': 'error', 'message': 'AI service error'})}\n\n"
                            return

                        async for line in response.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            raw = line[6:]  # strip "data: " prefix
                            try:
                                event = json.loads(raw)
                            except json.JSONDecodeError:
                                continue

                            etype = event.get("type")
                            if etype == "token":
                                full_text_parts.append(event.get("content", ""))

                            # Forward the event verbatim to the browser
                            yield f"data: {raw}\n\n"

                            if etype == "done":
                                full_text = "".join(full_text_parts).strip()
                                if full_text and session_obj:
                                    await _save_ai_message(session_obj, full_text)
                                return
                            elif etype == "error":
                                return

            except (httpx.TimeoutException, httpx.RequestError) as exc:
                logger.error("[chatbot:stream] FastAPI unreachable: %s", exc)
                yield f"data: {json.dumps({'type': 'error', 'message': 'AI service temporarily unavailable.'})}\n\n"
            except Exception as exc:
                logger.error("[chatbot:stream] unexpected error: %s", exc, exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': 'Internal server error.'})}\n\n"

        response = StreamingHttpResponse(sse_generator(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as exc:
        logger.error("[chatbot:stream] setup error: %s", exc, exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)


@require_http_methods(["GET"])
async def get_conversation_history(request):
    start = perf_counter()
    try:
        requested_session_id = request.GET.get("session_id")

        if requested_session_id:
            user = await _resolve_authenticated_user(request)
            if not user:
                return JsonResponse({"detail": "Authentication required"}, status=401)

            session_obj = await sync_to_async(
                ChatSession.objects.filter(user=user, session_id=requested_session_id).first
            )()
            if not session_obj:
                return JsonResponse({"detail": "Session not found"}, status=404)
        else:
            user, session_obj = await _get_or_create_session(request)

        if not user or not session_obj:
            return JsonResponse({"detail": "Authentication required"}, status=401)

        all_messages = await sync_to_async(list)(
            session_obj.messages.all().order_by("created_at")
        )

        messages_data = [
            {
                "id": msg.id,
                "sender": msg.sender,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in all_messages
        ]

        return JsonResponse({
            "session_id": session_obj.session_id,
            "user": str(user) if user else None,
            "user_id": getattr(user, "id", None),
            "message_count": len(messages_data),
            "messages": messages_data,
        })
    except Exception as e:
        logger.error("[chatbot] get_history error: %s", e, exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)
    finally:
        duration_ms = (perf_counter() - start) * 1000
        logger.info(
            "[chatbot] get_history session=%s duration_ms=%.2f",
            request.GET.get("session_id", "(auto)"), duration_ms,
        )


@csrf_exempt
@require_http_methods(["DELETE"])
async def clear_conversation_history(request):
    start = perf_counter()
    try:
        requested_session_id = request.GET.get("session_id")

        if requested_session_id:
            user = await _resolve_authenticated_user(request)
            if not user:
                return JsonResponse({"detail": "Authentication required"}, status=401)

            session_obj = await sync_to_async(
                ChatSession.objects.filter(user=user, session_id=requested_session_id).first)()
        else:
            user, session_obj = await _get_or_create_session(request)

        if not user or not session_obj:
            return JsonResponse({"detail": "Authentication required"}, status=401)

        deleted_count, _ = await sync_to_async(session_obj.delete, thread_sensitive=True)()
        logger.info("Deleted chat session %s for user %s", session_obj.session_id, getattr(user, "id", None))

        return JsonResponse({
            "status": "success",
            "deleted_count": deleted_count,
            "session_id": session_obj.session_id,
        })
    except Exception as e:
        logger.error("[chatbot] clear_history error: %s", e, exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)
    finally:
        duration_ms = (perf_counter() - start) * 1000
        logger.info("[chatbot] clear_history duration_ms=%.2f", duration_ms)


@csrf_exempt
@require_http_methods(["POST", "PATCH"])
async def rename_conversation_session(request):
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
            ChatSession.objects.filter(user=user, session_id=requested_session_id).first
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
        logger.error("[chatbot] rename_session error: %s", e, exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)
    finally:
        duration_ms = (perf_counter() - start) * 1000
        logger.info("[chatbot] rename_session duration_ms=%.2f", duration_ms)
