import datetime
import logging
from django.utils import timezone
from django.db.models.functions import TruncDate, Length, Cast, Coalesce
from django.db import models as dm
from django.db.models import Value
from apps.quiz.models import QuizSession

def _calculate_streak(user):
    """Consecutive days (ending today) with at least one study activity."""
    quiz_dates = (
        QuizSession.objects
        .filter(user=user)
        .annotate(day=TruncDate('created_at'))
        .values_list('day', flat=True)
        .distinct()
    )

    activity_days = set(d for d in quiz_dates if d)

    try:
        from apps.flashcards.models import Deck
        deck_dates = (
            Deck.objects
            .filter(user=user)
            .annotate(day=TruncDate('created_at'))
            .values_list('day', flat=True)
            .distinct()
        )
        activity_days.update(d for d in deck_dates if d)
    except Exception:
        pass

    try:
        from apps.chatbot.models import ChatSession
        chat_dates = (
            ChatSession.objects
            .filter(user=user)
            .annotate(day=TruncDate('created_at'))
            .values_list('day', flat=True)
            .distinct()
        )
        activity_days.update(d for d in chat_dates if d)
    except Exception:
        pass

    try:
        from apps.materials.models import Material
        material_dates = (
            Material.objects
            .filter(uploaded_by=user)
            .annotate(day=TruncDate('created_at'))
            .values_list('day', flat=True)
            .distinct()
        )
        activity_days.update(d for d in material_dates if d)
    except Exception:
        pass

    streak = 0
    today = timezone.now().date()
    while (today - datetime.timedelta(days=streak)) in activity_days:
        streak += 1
    return streak


def _tokens_from_chars(char_count: int) -> int:
    """
    Approximate token count from character count.
    Rule of thumb: ~4 characters/token for English mixed text.
    """
    if not char_count:
        return 0
    return int(round(char_count / 4))


# Conservative blended rate across DeepSeek / Claude / GPT-4 (~$2 per 1M tokens).
# Update this constant when provider mix changes significantly.
_BLENDED_COST_PER_1K_TOKENS = 0.002


def _cost_from_tokens(tokens: int) -> float:
    """Estimated USD cost from token count at blended provider rate."""
    if not tokens:
        return 0.0
    return round((tokens / 1000) * _BLENDED_COST_PER_1K_TOKENS, 4)


def _safe_char_sum(qs, expression):
    result = qs.aggregate(total=Coalesce(dm.Sum(expression), Value(0)))
    return int(result.get("total") or 0)



def _admin_activity_actor(user_obj):
    if not user_obj:
        return "Unknown user"
    return getattr(user_obj, "username", None) or getattr(user_obj, "email", "User")


def _collect_admin_activity(start_at=None, limit=50, offset=0):
    """Build merged activity timeline from quiz, flashcards, chat sessions, materials, and clashes."""
    from apps.flashcards.models import Deck
    from apps.materials.models import Material
    from apps.chatbot.models import ChatSession
    from apps.clash.models import ClashRoom

    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    fetch_size = min(max(limit + offset, 120), 600)

    recent_activity = []

    quizzes_qs = QuizSession.objects.select_related("user")
    decks_qs = Deck.objects.select_related("user")
    chats_qs = ChatSession.objects.select_related("user").annotate(message_count=dm.Count("messages"))
    materials_qs = Material.objects.select_related("uploaded_by")
    clashes_qs = ClashRoom.objects.select_related("host").annotate(
        participant_count=dm.Count("participants")
    ).filter(status=ClashRoom.FINISHED)

    if start_at is not None:
        quizzes_qs = quizzes_qs.filter(created_at__gte=start_at)
        decks_qs = decks_qs.filter(created_at__gte=start_at)
        chats_qs = chats_qs.filter(created_at__gte=start_at)
        materials_qs = materials_qs.filter(created_at__gte=start_at)
        clashes_qs = clashes_qs.filter(finished_at__gte=start_at)

    for quiz in quizzes_qs.order_by("-created_at")[:fetch_size]:
        subject = quiz.subject or "General"
        recent_activity.append(
            {
                "type": "quiz",
                "actor": _admin_activity_actor(quiz.user),
                "text": f"completed a {subject} quiz ({quiz.score_percentage}%)",
                "created_at": quiz.created_at,
            }
        )

    for deck in decks_qs.order_by("-created_at")[:fetch_size]:
        subject = deck.subject or "General"
        recent_activity.append(
            {
                "type": "flashcards",
                "actor": _admin_activity_actor(deck.user),
                "text": f"created flashcard deck '{deck.title}' ({subject})",
                "created_at": deck.created_at,
            }
        )

    for chat in chats_qs.order_by("-created_at")[:fetch_size]:
        msg_count = int(getattr(chat, "message_count", 0) or 0)
        recent_activity.append(
            {
                "type": "chat",
                "actor": _admin_activity_actor(chat.user),
                "text": f"started chat session ({msg_count} message{'s' if msg_count != 1 else ''})",
                "created_at": chat.created_at,
            }
        )

    for material in materials_qs.order_by("-created_at")[:fetch_size]:
        title = material.title or "Untitled"
        recent_activity.append(
            {
                "type": "material",
                "actor": _admin_activity_actor(material.uploaded_by),
                "text": f"uploaded material '{title}' ({material.file_size_display})",
                "created_at": material.created_at,
            }
        )

    for clash in clashes_qs.order_by("-finished_at")[:fetch_size]:
        n = int(getattr(clash, "participant_count", 0) or 0)
        recent_activity.append(
            {
                "type": "clash",
                "actor": _admin_activity_actor(clash.host),
                "text": f"hosted a Clash on '{clash.subject}' ({n} player{'s' if n != 1 else ''}, {clash.difficulty})",
                "created_at": clash.finished_at,
            }
        )

    recent_activity.sort(key=lambda item: item["created_at"], reverse=True)

    counts_by_type = {
        "quiz": 0,
        "flashcards": 0,
        "chat": 0,
        "material": 0,
        "clash": 0,
    }
    for item in recent_activity:
        item_type = item.get("type")
        if item_type in counts_by_type:
            counts_by_type[item_type] += 1

    total_count = len(recent_activity)
    page_items = recent_activity[offset: offset + limit]
    serialized = [
        {
            "type": item["type"],
            "actor": item["actor"],
            "text": item["text"],
            "created_at": item["created_at"].isoformat(),
        }
        for item in page_items
    ]
    return serialized, total_count, counts_by_type