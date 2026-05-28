import asyncio
import json
import logging
import httpx
from time import perf_counter
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from asgiref.sync import sync_to_async
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q
from .models import Deck, Flashcard
from .scheduling import update_sm2
from .serializers import (
    GenerateFlashcardsRequestSerializer,
    SaveDeckRequestSerializer,
    ReviewFlashcardRequestSerializer,
    ExplainFlashcardRequestSerializer,
    UpdateFlashcardRequestSerializer,
)
from apps.core.async_client import call_fastapi, build_fastapi_headers

logger = logging.getLogger(__name__)


async def _record_ai_latency(feature: str, duration_ms: int) -> None:
    try:
        from apps.dashboard.models import AIResponseLatency
        await sync_to_async(AIResponseLatency.objects.create)(
            feature=feature, duration_ms=duration_ms
        )
    except Exception:
        pass


def _parse_json_body(request):
    if not request.body:
        return None, JsonResponse({"error": "Request body is required"}, status=400)

    try:
        return json.loads(request.body), None
    except json.JSONDecodeError:
        return None, JsonResponse({"error": "Invalid JSON body"}, status=400)


def _serializer_error_response(serializer):
    return JsonResponse(
        {
            "error": "Invalid request data",
            "details": serializer.errors,
        },
        status=400,
    )

def _get_authenticated_user(request):
    """
    Authenticate API requests using DRF token auth.
    Returns (user, error_response). error_response is None on success.
    """
    try:
        auth_result = TokenAuthentication().authenticate(request)
    except AuthenticationFailed as exc:
        return None, JsonResponse({"detail": str(exc)}, status=401)

    if auth_result is None:
        return None, JsonResponse(
            {"detail": "Authentication credentials were not provided."},
            status=401
        )

    user, _token = auth_result
    if not user or not user.is_active:
        return None, JsonResponse({"detail": "Invalid user."}, status=401)

    return user, None


async def _get_authenticated_user_async(request):
    """
    Async-safe token authentication for async views.
    TokenAuthentication touches DB, so run in a thread.
    """
    try:
        auth_result = await sync_to_async(
            TokenAuthentication().authenticate,
            thread_sensitive=True
        )(request)
    except AuthenticationFailed as exc:
        return None, JsonResponse({"detail": str(exc)}, status=401)

    if auth_result is None:
        return None, JsonResponse(
            {"detail": "Authentication credentials were not provided."},
            status=401
        )

    user, _token = auth_result
    if not user or not user.is_active:
        return None, JsonResponse({"detail": "Invalid user."}, status=401)

    return user, None


@csrf_exempt
@require_POST
async def generate_flashcards(request):
    try:
        _user, auth_error = await _get_authenticated_user_async(request)
        if auth_error:
            return auth_error

        data, json_error = _parse_json_body(request)
        if json_error:
            return json_error

        serializer = GenerateFlashcardsRequestSerializer(data=data)
        if not serializer.is_valid():
            return _serializer_error_response(serializer)

        payload = serializer.validated_data

        _t0 = perf_counter()
        resp = await call_fastapi(
            "POST",
            "/flashcards/generate",
            timeout=30,
            headers=build_fastapi_headers(),
            json={
                "subject": payload["subject"],
                "text": payload["text"],
                "prompt": payload.get("prompt", ""),
                "num_cards": payload["num_cards"],
                "difficulty": payload["difficulty"],
            },
        )
        asyncio.create_task(_record_ai_latency('flashcards', int((perf_counter() - _t0) * 1000)))
        resp.raise_for_status()
        result = resp.json()

        if not isinstance(result, dict):
            logger.error("Unexpected flashcards/generate response type: %s", type(result).__name__)
            return JsonResponse({"error": "Invalid response from AI service"}, status=502)

        return JsonResponse(result)

    except httpx.TimeoutException:
        return JsonResponse({"error": "Flashcard generation timed out"}, status=504)
    except httpx.HTTPStatusError as exc:
        logger.warning("Flashcards upstream HTTP error: %s", exc)
        return JsonResponse({"error": "Flashcard generation service is unavailable"}, status=503)
    except httpx.RequestError as exc:
        logger.warning("Flashcards upstream request error: %s", exc)
        return JsonResponse({"error": "Unable to reach flashcard generation service"}, status=503)
    except Exception:
        logger.exception("Unexpected error in generate_flashcards")
        return JsonResponse({"error": "Failed to generate flashcards"}, status=500)
          
        
@csrf_exempt
@require_POST
def save_flashcard_deck(request):
    user, auth_error = _get_authenticated_user(request)
    if auth_error:
        return auth_error

    data, json_error = _parse_json_body(request)
    if json_error:
        return json_error

    serializer = SaveDeckRequestSerializer(data=data)
    if not serializer.is_valid():
        return _serializer_error_response(serializer)

    payload = serializer.validated_data

    try:
        with transaction.atomic():
            deck = Deck.objects.create(
                user=user,
                title=payload["subject"],
                subject=payload["subject"],
            )

            cards = payload["cards"]
            objs = [
                Flashcard(
                    deck=deck,
                    question=c["question"],
                    answer=c["answer"],
                )
                for c in cards
            ]

            Flashcard.objects.bulk_create(objs)

        return JsonResponse({"deck_id": deck.id}, status=201)
    except Exception:
        logger.exception("Failed to save flashcard deck for user_id=%s", user.id)
        return JsonResponse({"error": "Failed to save flashcard deck"}, status=500)
    

def get_decks(request):
    user, auth_error = _get_authenticated_user(request)
    if auth_error:
        return auth_error

    try:
        now = timezone.now()
        decks = Deck.objects.filter(user=user).annotate(
            card_count=Count("cards"),
            due_today=Count("cards", filter=Q(cards__next_review__lte=now)),
        ).order_by("-created_at")

        # Pagination support
        page = request.GET.get("page", 1)
        page_size = request.GET.get("page_size", 20)

        try:
            page = int(page)
            page_size = min(int(page_size), 100)  # Max 100 per page
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid pagination parameters"}, status=400)

        paginator = Paginator(decks, page_size)

        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return JsonResponse(
            {
                "decks": [
                    {
                        "id": d.id,
                        "title": d.title,
                        "created_at": d.created_at.isoformat(),
                        "card_count": d.card_count,
                        "due_today": d.due_today,
                    }
                    for d in page_obj
                ],
                "pagination": {
                    "current_page": page_obj.number,
                    "total_pages": paginator.num_pages,
                    "total_count": paginator.count,
                    "page_size": page_size,
                    "has_next": page_obj.has_next(),
                    "has_previous": page_obj.has_previous(),
                }
            }
        )
    except Exception:
        logger.exception("Failed to fetch decks for user_id=%s", user.id)
        return JsonResponse({"error": "Failed to fetch decks"}, status=500)


def get_flashcards_history(request):
    user, auth_error = _get_authenticated_user(request)
    if auth_error:
        return auth_error

    try:
        decks = (
            Deck.objects.filter(user=user)
            .annotate(card_count=Count("cards"))
            .order_by("-created_at")[:30]
        )

        return JsonResponse(
            {
                "history": [
                    {
                        "id": d.id,
                        "title": d.title,
                        "subject": d.subject,
                        "card_count": d.card_count,
                        "created_at": d.created_at.isoformat(),
                    }
                    for d in decks
                ]
            }
        )
    except Exception:
        logger.exception("Failed to fetch flashcards history for user_id=%s", user.id)
        return JsonResponse({"error": "Failed to fetch flashcards history"}, status=500)
    
@csrf_exempt
@require_http_methods(["GET", "DELETE"])
def get_deck_cards(request, deck_id):
    user, auth_error = _get_authenticated_user(request)
    if auth_error:
        return auth_error

    deck = Deck.objects.filter(id=deck_id, user=user).first()

    if request.method == "DELETE":
        if not deck:
            return JsonResponse({"error": "Deck not found"}, status=404)

        try:
            deck.delete()
            return JsonResponse({"status": "deleted"})
        except Exception:
            logger.exception("Failed to delete deck_id=%s for user_id=%s", deck_id, user.id)
            return JsonResponse({"error": "Failed to delete deck"}, status=500)

    if not deck:
        return JsonResponse({"error": "Deck not found"}, status=404)

    try:
        cards = Flashcard.objects.filter(
            deck_id=deck_id,
            deck__user=user,
        ).values("id", "question", "answer")

        return JsonResponse(
            {
                "title": deck.title,
                "cards": list(cards),
            }
        )
    except Exception:
        logger.exception("Failed to fetch deck cards for deck_id=%s user_id=%s", deck_id, user.id)
        return JsonResponse({"error": "Failed to fetch deck cards"}, status=500)
    
@csrf_exempt
@require_POST
def review_flashcard(request):
    user, auth_error = _get_authenticated_user(request)
    if auth_error:
        return auth_error

    try:
        data, json_error = _parse_json_body(request)
        if json_error:
            return json_error

        serializer = ReviewFlashcardRequestSerializer(data=data)
        if not serializer.is_valid():
            return _serializer_error_response(serializer)

        payload = serializer.validated_data

        card = Flashcard.objects.get(
            id=payload["card_id"],
            deck__user=user,
        )

        update_sm2(card, payload["quality"])
        return JsonResponse({"status": "updated"})
    except Flashcard.DoesNotExist:
        return JsonResponse({"error": "Flashcard not found"}, status=404)
    except Exception:
        logger.exception("Failed to review flashcard for user_id=%s", user.id)
        return JsonResponse({"error": "Failed to review flashcard"}, status=500)


@csrf_exempt
@require_POST
async def explain_flashcard(request):
    user, auth_error = await _get_authenticated_user_async(request)
    if auth_error:
        return auth_error

    try:
        data, json_error = _parse_json_body(request)
        if json_error:
            return json_error

        serializer = ExplainFlashcardRequestSerializer(data=data)
        if not serializer.is_valid():
            return _serializer_error_response(serializer)

        payload = serializer.validated_data
        card_id = payload.get("card_id")
        
        # If card_id is provided, check cache first
        if card_id:
            try:
                card = await sync_to_async(Flashcard.objects.get)(
                    id=card_id,
                    deck__user=user,
                )
                
                # Return cached explanation if available
                if card.explanation:
                    return JsonResponse({"explanation": card.explanation})
                
                # Use card's question and answer
                question = card.question
                answer = card.answer
            except Flashcard.DoesNotExist:
                return JsonResponse({"error": "Flashcard not found"}, status=404)
        else:
            # Use provided question and answer
            question = payload["question"]
            answer = payload["answer"]

        # Fetch explanation from AI service
        resp = await call_fastapi(
            "POST",
            "/flashcards/explain",
            timeout=40,
            headers=build_fastapi_headers(),
            json={
                "question": question,
                "answer": answer,
            },
        )
        resp.raise_for_status()
        result = resp.json()

        if not isinstance(result, dict):
            logger.error("Unexpected flashcards/explain response type: %s", type(result).__name__)
            return JsonResponse({"error": "Invalid response from AI service"}, status=502)

        # Cache the explanation if card_id was provided
        if card_id and "explanation" in result:
            card.explanation = result["explanation"]
            await sync_to_async(card.save)(update_fields=["explanation"])

        return JsonResponse(result)
    except httpx.TimeoutException:
        return JsonResponse({"error": "Flashcard explanation timed out"}, status=504)
    except httpx.HTTPStatusError as exc:
        logger.warning("Flashcards explain upstream HTTP error: %s", exc)
        return JsonResponse({"error": "Flashcard explanation service is unavailable"}, status=503)
    except httpx.RequestError as exc:
        logger.warning("Flashcards explain upstream request error: %s", exc)
        return JsonResponse({"error": "Unable to reach flashcard explanation service"}, status=503)
    except Exception:
        logger.exception("Unexpected error in explain_flashcard")
        return JsonResponse({"error": "Failed to explain flashcard"}, status=500)


@csrf_exempt
@require_POST
def update_flashcard(request):
    """Update a flashcard's question and answer."""
    user, auth_error = _get_authenticated_user(request)
    if auth_error:
        return auth_error

    try:
        data, json_error = _parse_json_body(request)
        if json_error:
            return json_error

        serializer = UpdateFlashcardRequestSerializer(data=data)
        if not serializer.is_valid():
            return _serializer_error_response(serializer)

        payload = serializer.validated_data

        card = Flashcard.objects.select_for_update().get(
            id=payload["card_id"],
            deck__user=user,
        )

        card.question = payload["question"]
        card.answer = payload["answer"]
        card.save(update_fields=["question", "answer"])

        return JsonResponse({
            "status": "updated",
            "card": {
                "id": card.id,
                "question": card.question,
                "answer": card.answer,
            }
        })
    except Flashcard.DoesNotExist:
        return JsonResponse({"error": "Flashcard not found"}, status=404)
    except Exception:
        logger.exception("Failed to update flashcard for user_id=%s", user.id)
        return JsonResponse({"error": "Failed to update flashcard"}, status=500)


@csrf_exempt
@require_http_methods(["DELETE", "POST"])
def delete_flashcard(request, card_id):
    """Delete a specific flashcard."""
    user, auth_error = _get_authenticated_user(request)
    if auth_error:
        return auth_error

    try:
        card = Flashcard.objects.get(
            id=card_id,
            deck__user=user,
        )

        deck_id = card.deck_id
        card.delete()

        return JsonResponse({
            "status": "deleted",
            "deck_id": deck_id,
        })
    except Flashcard.DoesNotExist:
        return JsonResponse({"error": "Flashcard not found"}, status=404)
    except Exception:
        logger.exception("Failed to delete flashcard card_id=%s for user_id=%s", card_id, user.id)
        return JsonResponse({"error": "Failed to delete flashcard"}, status=500)
