import logging
import time
from datetime import datetime
from asgiref.sync import sync_to_async
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import ChatSession, ChatMessage
from .prompts import (
    SOCRATIC_MODE_INSTRUCTIONS,
    STATIC_PLATFORM_FACTS,
    TUTOR_BEHAVIOR_GUIDE,
    TUTOR_PERSONA_INTRO,
    TOOL_USE_GUIDANCE,
    wrap_document_context,
)

logger = logging.getLogger(__name__)


def _derive_session_title(user_message: str) -> str:
    text = (user_message or "").strip().replace("\n", " ")
    if not text:
        return "New chat"

    sentence_end = len(text)
    for separator in (". ", "? ", "! ", ".", "?", "!"):
        index = text.find(separator)
        if index != -1:
            sentence_end = min(sentence_end, index + (0 if separator in {'.', '?', '!'} else 1))

    title = text[:sentence_end].strip().strip('"\'')
    if len(title) > 120:
        title = title[:117].rstrip() + "..."
    return title or "New chat"


def _prune_old_chat_sessions_sync(user, keep: int = 10, preserve_session_pk=None):
    """Keep only the newest `keep` sessions for a user, deleting older ones."""
    sessions_qs = ChatSession.objects.filter(user=user).order_by("-created_at", "-id")
    keep_ids = list(sessions_qs.values_list("id", flat=True)[:keep])

    if preserve_session_pk is not None:
        keep_ids.append(preserve_session_pk)

    deleted_count, _ = ChatSession.objects.filter(user=user).exclude(id__in=set(keep_ids)).delete()
    return deleted_count


async def _resolve_authenticated_user(request):
    """
    Resolve authenticated user for non-DRF async Django views.
    Uses DRF token auth only to avoid touching lazy request.user/session
    in async context.
    """
    auth_header = request.headers.get("Authorization", "").strip()
    if not auth_header:
        return None

    try:
        auth_result = await sync_to_async(
            TokenAuthentication().authenticate,
            thread_sensitive=True,
        )(request)
    except AuthenticationFailed:
        return None
    except Exception:
        logger.exception(
            "Token authentication failed in chatbot session resolver")
        return None

    if not auth_result:
        return None

    user, _token = auth_result
    return user if user and user.is_active else None


async def _get_or_create_session(request, session_id=None):
    """
    Get/create chat session for authenticated users.

    If session_id is provided, use that session (allows multiple sessions per user).
    If session_id is None, create a new session.
    """
    user = await _resolve_authenticated_user(request)

    if user:
        if session_id is None:
            # No session specified - shouldn't happen, but create new one
            session_id = f"chat-{user.id}-{int(time.time())}"

        # Get or create session with the provided session_id
        session_obj, created = await sync_to_async(ChatSession.objects.get_or_create)(
            session_id=session_id,
            defaults={"user": user},
        )

        # Self-heal: ensure session is linked to user
        if session_obj.user_id != user.id:
            session_obj.user = user
            await sync_to_async(session_obj.save, thread_sensitive=True)(update_fields=["user"])

        if created:
            logger.debug(f"Created new session {session_id} for user {user.id}")

        # Enforce retention policy: keep only 10 newest sessions per user.
        deleted_count = await sync_to_async(_prune_old_chat_sessions_sync, thread_sensitive=True)(
            user,
            keep=10,
            preserve_session_pk=session_obj.id,
        )
        if deleted_count:
            logger.info(
                "Pruned %s old chat session(s) for user %s",
                deleted_count,
                user.id,
            )

        return user, session_obj

    return None, None


async def _save_user_message(session_obj, user_message: str):
    """Save user message to DB for authenticated sessions only."""
    if session_obj is None:
        return None
    try:
        msg_obj = await sync_to_async(ChatMessage.objects.create)(
            session=session_obj,
            sender="user",
            content=user_message,
        )
        logger.debug("Saved user message ID %s to session %s",
                     msg_obj.id, session_obj.id)

        if not getattr(session_obj, "title", ""):
            session_obj.title = _derive_session_title(user_message)
            await sync_to_async(session_obj.save, thread_sensitive=True)(update_fields=["title"])

        return msg_obj
    except Exception as exc:
        logger.error("Failed to save user message: %s", exc, exc_info=True)
        raise


async def _save_ai_message(session_obj, ai_message: str):
    """Save AI message to DB for authenticated sessions only."""
    if session_obj is None:
        return None
    try:
        msg_obj = await sync_to_async(ChatMessage.objects.create)(
            session=session_obj,
            sender="ai",
            content=ai_message,
        )
        logger.debug("Saved AI message ID %s to session %s",
                     msg_obj.id, session_obj.id)
        return msg_obj
    except Exception as exc:
        logger.error("Failed to save AI message: %s", exc, exc_info=True)
        raise


async def _get_conversation_history(session_obj, limit: int = 10):
    """
    Get conversation history for context.
    """
    if session_obj is None:
        return []

    history_qs = await sync_to_async(list)(session_obj.messages.order_by("-created_at")[:limit])
    conversation_history = []
    for msg in reversed(history_qs):
        conversation_history.append(
            {"message_type": msg.sender, "content": msg.content})
    return conversation_history


def fallback_response(user_message: str) -> str:
    """Static fallback when the AI service is unavailable."""
    msg = user_message.lower()
    if any(w in msg for w in ['hello', 'hi', 'hey']):
        return (
            "Hello! I'm Lamla AI Tutor. I'm here to help with platform questions, "
            "study tips, and general topics. What would you like to know today?"
        )
    if any(w in msg for w in ['feature', 'quiz', 'flashcard']):
        return (
            "Lamla AI offers quiz generation, flashcard creation, performance tracking, "
            "and study material uploads (PDF, PPTX, DOCX). "
            "Visit https://lamla-ai.vercel.app to explore all features."
        )
    if any(w in msg for w in ['contact', 'support', 'email']):
        return (
            "You can reach the Lamla team at lamlaaiteam@gmail.com "
            "or WhatsApp +233509341251. We usually respond within 24 hours."
        )
    if any(w in msg for w in ['thank', 'thanks']):
        return "You're welcome! Let me know if you have any other questions."
    return (
        "I'm Lamla AI Tutor. I can help with platform navigation, study tools, "
        "and general questions. What would you like to know?"
    )


def _fetch_user_performance_sync(user) -> dict | None:
    """
    Fetch a compact performance snapshot for the authenticated user.
    Returns None if the user has no quiz history (nothing to inject).
    Three cheap queries: aggregate stats, weak areas, due topics.
    """
    try:
        from django.db.models import Avg, Count
        from django.utils import timezone
        from apps.quiz.models import QuizSession, TopicPerformance, QuizTopicSchedule

        agg = QuizSession.objects.filter(user=user).aggregate(
            total=Count('id'), avg_score=Avg('score_percentage')
        )
        total_quizzes = agg['total'] or 0
        if total_quizzes == 0:
            return None  # no history — skip injection entirely

        avg_score = round(float(agg['avg_score'] or 0), 1)

        qs = TopicPerformance.objects.filter(user=user, total_questions__gte=3)

        weak = list(
            qs.order_by('accuracy')[:3]
            .values_list('topic', 'accuracy')
        )

        strong = list(
            qs.order_by('-accuracy')[:3]
            .values_list('topic', 'accuracy')
        )

        due = list(
            QuizTopicSchedule.objects.filter(user=user, next_review__lte=timezone.now())
            .order_by('next_review')[:3]
            .values_list('topic', flat=True)
        )

        return {
            'total_quizzes': total_quizzes,
            'avg_score': avg_score,
            'weak_areas': [(t, round(a, 1)) for t, a in weak],
            'strong_areas': [(t, round(a, 1)) for t, a in strong],
            'due_topics': due,
        }
    except Exception:
        logger.exception("Failed to fetch user performance for chatbot prompt")
        return None


def _format_performance_block(perf: dict) -> str:
    """Format the performance dict into a compact prompt-safe block."""
    lines = [
        f"[{perf['total_quizzes']} quizzes taken | Avg score: {perf['avg_score']}%]",
    ]
    if perf.get('weak_areas'):
        topics = ', '.join(f"{t} ({a}%)" for t, a in perf['weak_areas'])
        lines.append(f"Weak topics: {topics}")
    if perf.get('strong_areas'):
        topics = ', '.join(f"{t} ({a}%)" for t, a in perf['strong_areas'])
        lines.append(f"Strong topics: {topics}")
    if perf.get('due_topics'):
        lines.append(f"Due for review: {', '.join(perf['due_topics'])}")
    return "Student learning progress:\n" + "\n".join(lines) + "\n"


def _build_system_prompt(
    platform_context: str,
    user=None,
    user_performance: dict | None = None,
    context_document: str = "",
    tutor_mode: str = "direct",
    include_tool_guidance: bool = False,
) -> str:
    """
    Single source of truth for the Lamla system prompt.

    Both _build_chatbot_prompt (one-shot) and _build_mcp_context (tool loop)
    call this. All text constants come from prompts.py — nothing is defined
    inline here.

    platform_context  -- retrieved KB chunks (from text_knowledge_store)
    user_performance  -- compact perf snapshot from _fetch_user_performance_sync (or None)
    context_document  -- optional uploaded file content
    tutor_mode        -- "direct" (default) or "socratic"
    include_tool_guidance -- True only for MCP/orchestrate paths
    """
    user_name = getattr(user, "username", None) if user else None
    user_line = ""
    if user_name:
        label = "superuser/platform manager" if user_name.lower() == "admin" else "student"
        user_line = f"Current user: {user_name} ({label}).\n"

    perf_section = _format_performance_block(user_performance) + "\n" if user_performance else ""
    doc_section = wrap_document_context(context_document) if context_document else ""
    socratic_section = SOCRATIC_MODE_INSTRUCTIONS if tutor_mode == "socratic" else ""
    tool_section = TOOL_USE_GUIDANCE if include_tool_guidance else ""

    return (
        f"{TUTOR_PERSONA_INTRO}\n\n"
        f"{STATIC_PLATFORM_FACTS}\n"
        f"{user_line}"
        f"{perf_section}"
        f"Date/time: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"{doc_section}"
        f"PLATFORM KNOWLEDGE BASE:\n{platform_context}\n\n"
        f"{TUTOR_BEHAVIOR_GUIDE}"
        f"{socratic_section}"
        f"{tool_section}"
    )


async def _build_chatbot_prompt(
    user_message: str,
    conversation_history=None,
    context_document: str = "",
    user=None,
    tutor_mode: str = "direct",
) -> str:
    """One-shot prompt string for POST /chatbot/ (classic path)."""
    from .text_knowledge_store import knowledge_store
    platform_context = await sync_to_async(knowledge_store.get_context)(user_message, top_k=6)

    user_performance = None
    if user:
        user_performance = await sync_to_async(_fetch_user_performance_sync, thread_sensitive=True)(user)

    # Never embed the document inside the system block — it gets "lost in the middle"
    # of a long prompt and LLMs stop attending to it. Instead we inject it right
    # before the question so it sits at the end of the context where attention is highest.
    system_prompt = _build_system_prompt(
        platform_context=platform_context,
        user=user,
        user_performance=user_performance,
        context_document="",          # document injected below, not here
        tutor_mode=tutor_mode,
        include_tool_guidance=False,
    )

    history_text = ""
    if conversation_history:
        for msg in conversation_history:
            role = "User" if msg["message_type"] == "user" else "AI"
            history_text += f"{role}: {msg['content']}\n"

    # Place document immediately before the question for maximum LLM attention
    doc_block = wrap_document_context(context_document) if context_document else ""

    return (
        f"{system_prompt}\n\n"
        f"Previous Conversation:\n{history_text}\n"
        f"{doc_block}"
        f"Student Question: {user_message}\n\n"
        f"AI Tutor Response:"
    )


async def _build_mcp_context(
    user_message: str,
    conversation_history=None,
    user=None,
) -> tuple[str, list[dict]]:
    """
    MCP / tool-loop variant. Returns (system_prompt, messages).

    system_prompt  -- persona + KB + tool guidance (no history — goes in messages)
    messages       -- Anthropic [{role, content}] list, current user turn last
    """
    from .text_knowledge_store import knowledge_store
    platform_context = await sync_to_async(knowledge_store.get_context)(user_message, top_k=6)

    user_performance = None
    if user:
        user_performance = await sync_to_async(_fetch_user_performance_sync, thread_sensitive=True)(user)

    system_prompt = _build_system_prompt(
        platform_context=platform_context,
        user=user,
        user_performance=user_performance,
        include_tool_guidance=True,
    )

    messages: list[dict] = []
    if conversation_history:
        for msg in conversation_history:
            role = "user" if msg["message_type"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    return system_prompt, messages
