import json
import logging

from asgiref.sync import sync_to_async
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils.html import escape as html_escape
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.core.async_client import call_fastapi, build_fastapi_headers
from .models import ClashRoom, ClashParticipant, MAX_PARTICIPANTS, VALID_TIME_OPTIONS

logger = logging.getLogger(__name__)


async def _authenticate(request):
    try:
        result = await sync_to_async(
            TokenAuthentication().authenticate, thread_sensitive=True
        )(request)
    except AuthenticationFailed as exc:
        return None, JsonResponse({"detail": str(exc)}, status=401)
    if not result:
        return None, JsonResponse({"detail": "Authentication required."}, status=401)
    user, _ = result
    if not user.is_active:
        return None, JsonResponse({"detail": "Invalid user."}, status=401)
    return user, None


@csrf_exempt
@require_http_methods(["POST"])
async def create_clash(request):
    """
    Create a Clash room.
    Generates MCQ questions via FastAPI, saves the room, adds host as first participant.
    """
    user, err = await _authenticate(request)
    if err:
        return err

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON."}, status=400)

    subject = (data.get("subject") or "").strip()
    difficulty = (data.get("difficulty") or "medium").strip().lower()
    num_questions = int(data.get("num_questions") or 10)
    time_per_question = int(data.get("time_per_question") or 20)
    provided_text = (data.get("study_text") or "").strip()

    if not subject:
        return JsonResponse({"detail": "Subject is required."}, status=400)
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"
    num_questions = max(5, min(num_questions, 20))
    if time_per_question not in VALID_TIME_OPTIONS:
        time_per_question = 20

    if len(provided_text) >= 50:
        study_text = provided_text
    else:
        study_text = (
            f"Generate a {difficulty} quiz on {subject}. "
            f"Use broad general knowledge of {subject}. "
            f"Cover varied subtopics so players with different preparation levels all encounter something familiar."
        )

    try:
        fastapi_resp = await call_fastapi(
            "POST",
            "/quiz/",
            json={
                "subject": subject,
                "study_text": study_text,
                "num_mcq": num_questions,
                "num_short": 0,
                "difficulty": difficulty,
                "source_type": "text",
            },
            headers=build_fastapi_headers(),
            timeout=120.0,
        )
    except Exception as exc:
        logger.error("FastAPI quiz generation failed for Clash: %s", exc)
        return JsonResponse({"detail": "Quiz service unavailable. Try again."}, status=503)

    if fastapi_resp.status_code != 200:
        logger.error("FastAPI /quiz/ returned %s", fastapi_resp.status_code)
        return JsonResponse({"detail": "Question generation failed."}, status=502)

    quiz_data = fastapi_resp.json()
    questions = quiz_data.get("mcq_questions", [])[:num_questions]

    if not questions:
        return JsonResponse({"detail": "No questions were generated. Try a different subject."}, status=502)

    room = await sync_to_async(ClashRoom.objects.create)(
        host=user,
        subject=subject,
        difficulty=difficulty,
        questions=questions,
        num_questions=len(questions),
        time_per_question=time_per_question,
    )
    await sync_to_async(ClashParticipant.objects.create)(
        room=room,
        user=user,
        display_name=user.username,
        is_host=True,
    )

    logger.info("Clash room %s created by %s (%d questions)", room.room_code, user.username, len(questions))
    return JsonResponse({
        "room_code": room.room_code,
        "subject": room.subject,
        "difficulty": room.difficulty,
        "num_questions": room.num_questions,
        "time_per_question": room.time_per_question,
    }, status=201)


@csrf_exempt
@require_http_methods(["POST"])
async def join_clash(request):
    """Join an existing waiting Clash room by code."""
    user, err = await _authenticate(request)
    if err:
        return err

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON."}, status=400)

    room_code = (data.get("room_code") or "").strip().upper()
    if not room_code:
        return JsonResponse({"detail": "Room code is required."}, status=400)

    try:
        room = await sync_to_async(ClashRoom.objects.select_related('host').get)(room_code=room_code)
    except ClashRoom.DoesNotExist:
        return JsonResponse({"detail": "Room not found. Check the code and try again."}, status=404)

    if room.status == ClashRoom.FINISHED:
        return JsonResponse({"detail": "This Clash has already ended."}, status=400)
    if room.status == ClashRoom.ACTIVE:
        return JsonResponse({"detail": "This Clash is already in progress."}, status=400)

    # Check if already a participant (rejoin scenario)
    existing = await sync_to_async(
        ClashParticipant.objects.filter(room=room, user=user).first
    )()
    if existing:
        return JsonResponse({
            "room_code": room.room_code,
            "subject": room.subject,
            "difficulty": room.difficulty,
            "num_questions": room.num_questions,
            "time_per_question": room.time_per_question,
            "is_host": existing.is_host,
        })

    count = await sync_to_async(room.participants.count)()
    if count >= MAX_PARTICIPANTS:
        return JsonResponse({"detail": f"Room is full (max {MAX_PARTICIPANTS} players)."}, status=400)

    participant = await sync_to_async(ClashParticipant.objects.create)(
        room=room,
        user=user,
        display_name=user.username,
        is_host=False,
    )

    return JsonResponse({
        "room_code": room.room_code,
        "subject": room.subject,
        "difficulty": room.difficulty,
        "num_questions": room.num_questions,
        "time_per_question": room.time_per_question,
        "is_host": participant.is_host,
    })


@csrf_exempt
@require_http_methods(["GET"])
async def room_info(request, room_code):
    """Lobby info — participant list, room metadata, status."""
    user, err = await _authenticate(request)
    if err:
        return err

    try:
        room = await sync_to_async(
            ClashRoom.objects.select_related('host').get
        )(room_code=room_code.upper())
    except ClashRoom.DoesNotExist:
        return JsonResponse({"detail": "Room not found."}, status=404)

    participants = await sync_to_async(list)(
        room.participants.select_related('user').all()
    )

    return JsonResponse({
        "room_code": room.room_code,
        "subject": room.subject,
        "difficulty": room.difficulty,
        "num_questions": room.num_questions,
        "time_per_question": room.time_per_question,
        "status": room.status,
        "host_username": room.host.username,
        "participants": [
            {
                "username": p.user.username,
                "display_name": p.display_name,
                "is_host": p.is_host,
                "profile_image": p.user.profile_image or "",
            }
            for p in participants
        ],
    })


@csrf_exempt
@require_http_methods(["GET"])
async def my_clashes(request):
    """Current user's finished Clash participations, newest first."""
    user, err = await _authenticate(request)
    if err:
        return err

    participations = await sync_to_async(list)(
        ClashParticipant.objects
        .filter(user=user, room__status=ClashRoom.FINISHED)
        .select_related('room', 'room__host')
        .order_by('-room__finished_at')
    )

    # Total participants per room (need one extra query per room — batch it)
    room_ids = [p.room_id for p in participations]
    counts_qs = await sync_to_async(list)(
        ClashParticipant.objects
        .filter(room_id__in=room_ids)
        .values('room_id')
    )
    from collections import Counter
    player_counts = Counter(c['room_id'] for c in counts_qs)

    return JsonResponse({
        "clashes": [
            {
                "room_code": p.room.room_code,
                "subject": p.room.subject,
                "difficulty": p.room.difficulty,
                "num_questions": p.room.num_questions,
                "score": p.score,
                "rank": p.rank,
                "player_count": player_counts.get(p.room_id, 1),
                "is_host": p.is_host,
                "finished_at": p.room.finished_at.isoformat() if p.room.finished_at else None,
            }
            for p in participations
        ]
    })


@csrf_exempt
@require_http_methods(["GET"])
async def admin_clash_list(request):
    """Admin: list all Clash rooms with summary stats."""
    user, err = await _authenticate(request)
    if err:
        return err
    if not (user.is_staff or user.is_superuser):
        return JsonResponse({"detail": "Admin access required."}, status=403)

    rooms = await sync_to_async(list)(
        ClashRoom.objects.select_related('host').prefetch_related('participants').order_by('-created_at')
    )

    results = []
    for room in rooms:
        participants = await sync_to_async(list)(
            room.participants.select_related('user').order_by('rank', '-score')
        )
        winner = None
        for p in participants:
            if p.rank == 1:
                winner = {"username": p.user.username, "display_name": p.display_name, "score": p.score}
                break

        results.append({
            "room_code": room.room_code,
            "subject": room.subject,
            "difficulty": room.difficulty,
            "num_questions": room.num_questions,
            "time_per_question": room.time_per_question,
            "status": room.status,
            "host_username": room.host.username,
            "participant_count": len(participants),
            "winner": winner,
            "created_at": room.created_at.isoformat(),
            "started_at": room.started_at.isoformat() if room.started_at else None,
            "finished_at": room.finished_at.isoformat() if room.finished_at else None,
        })

    return JsonResponse({"clashes": results})


@csrf_exempt
@require_http_methods(["GET"])
async def admin_clash_detail(request, room_code):
    """Admin: full detail for one Clash room."""
    user, err = await _authenticate(request)
    if err:
        return err
    if not (user.is_staff or user.is_superuser):
        return JsonResponse({"detail": "Admin access required."}, status=403)

    try:
        room = await sync_to_async(
            ClashRoom.objects.select_related('host').get
        )(room_code=room_code.upper())
    except ClashRoom.DoesNotExist:
        return JsonResponse({"detail": "Room not found."}, status=404)

    participants = await sync_to_async(list)(
        room.participants.select_related('user').order_by('rank', '-score', 'joined_at')
    )

    return JsonResponse({
        "room_code": room.room_code,
        "subject": room.subject,
        "difficulty": room.difficulty,
        "num_questions": room.num_questions,
        "time_per_question": room.time_per_question,
        "status": room.status,
        "host_username": room.host.username,
        "created_at": room.created_at.isoformat(),
        "started_at": room.started_at.isoformat() if room.started_at else None,
        "finished_at": room.finished_at.isoformat() if room.finished_at else None,
        "participants": [
            {
                "rank": p.rank,
                "username": p.user.username,
                "display_name": p.display_name,
                "score": p.score,
                "is_host": p.is_host,
                "correct": sum(1 for a in (p.answers or []) if a.get("correct")),
                "joined_at": p.joined_at.isoformat(),
            }
            for p in participants
        ],
    })


@csrf_exempt
@require_http_methods(["GET"])
async def clash_results(request, room_code):
    """Final leaderboard for a finished Clash."""
    user, err = await _authenticate(request)
    if err:
        return err

    try:
        room = await sync_to_async(ClashRoom.objects.get)(room_code=room_code.upper())
    except ClashRoom.DoesNotExist:
        return JsonResponse({"detail": "Room not found."}, status=404)

    participants = await sync_to_async(list)(
        room.participants.select_related('user').order_by('-score', 'joined_at')
    )

    return JsonResponse({
        "room_code": room.room_code,
        "subject": room.subject,
        "difficulty": room.difficulty,
        "num_questions": room.num_questions,
        "status": room.status,
        "rankings": [
            {
                "rank": idx + 1,
                "username": p.user.username,
                "display_name": p.display_name,
                "score": p.score,
                "is_host": p.is_host,
                "correct": sum(1 for a in p.answers if a.get("correct")),
                "profile_image": p.user.profile_image or "",
            }
            for idx, p in enumerate(participants)
        ],
    })


@csrf_exempt
@require_http_methods(["GET"])
async def clash_share_preview(request, room_code):
    """
    Open Graph preview page for Clash invite links.

    Bots (WhatsApp, iMessage, Twitter, etc.) crawl this URL and see the
    Clash-specific OG tags with clash-fist.jpg. Real users are instantly
    redirected to the SPA via meta-refresh.
    """
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    room_code = room_code.upper()
    redirect_url = f"{frontend_url}/clash?join={room_code}"
    image_url = f"{frontend_url}/assets/clash-fist.jpg"

    # Try to enrich the title/description with the actual subject
    og_title = "Join a Clash on Lamla AI!"
    og_desc = (
        f"You've been invited to a live quiz battle on Lamla AI. "
        f"Join room {room_code} and compete now!"
    )
    try:
        room = await sync_to_async(ClashRoom.objects.get)(room_code=room_code)
        if room.subject:
            og_title = f"Clash: {room.subject} — Join the battle!"
            og_desc = (
                f"You've been challenged to a live {room.subject} quiz battle "
                f"on Lamla AI. Join room {room_code} and compete!"
            )
    except ClashRoom.DoesNotExist:
        pass

    t = html_escape(og_title)
    d = html_escape(og_desc)
    share_url = html_escape(request.build_absolute_uri())

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Lamla AI">
  <meta property="og:title" content="{t}">
  <meta property="og:description" content="{d}">
  <meta property="og:image" content="{image_url}">
  <meta property="og:image:alt" content="Lamla AI Clash — Live Quiz Battle">
  <meta property="og:url" content="{share_url}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{t}">
  <meta name="twitter:description" content="{d}">
  <meta name="twitter:image" content="{image_url}">
  <meta http-equiv="refresh" content="0;url={redirect_url}">
  <title>{t}</title>
</head>
<body>
  <p>Redirecting to Lamla AI Clash…</p>
  <a href="{redirect_url}">Click here if not redirected</a>
</body>
</html>"""

    return HttpResponse(html, content_type="text/html")
