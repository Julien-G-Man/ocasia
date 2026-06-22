import datetime
import logging
from django.core.cache import cache
from django.utils import timezone
from django.db import models as dm
from django.db.models import Value, TextField
from django.db.models.functions import TruncDate, Length, Cast, Coalesce
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from apps.quiz.models import QuizSession
from apps.chatbot.models import ChatSession, ChatMessage
from apps.accounts.serializers import user_to_dict
from apps.accounts.services import EmailDeliveryError
from .models import QuizExperienceRating, AnonymousUsageEvent, AIResponseLatency
from .serializers import ContactFormSerializer, NewsletterSerializer, QuizFeedbackSerializer
from .services import send_contact_emails, send_newsletter_emails
from .helpers import _calculate_streak, _tokens_from_chars, _safe_char_sum, _collect_admin_activity, _cost_from_tokens


logger = logging.getLogger(__name__)


class IsAdminUser(BasePermission):
    """Permission class to check if user is an admin."""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and getattr(request.user, 'is_admin', False)


class ContactThrottle(SimpleRateThrottle):
    """10 contact/newsletter submissions per hour per IP."""
    scope = 'contact'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class DashboardStatsView(APIView):
    """GET /api/dashboard/stats/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        cache_key = f'dash:stats:{user.id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        quiz_stats = QuizSession.objects.filter(user=user).aggregate(
            total=dm.Count('id'),
            avg=dm.Avg('score_percentage'),
        )

        total_flashcard_sets = 0
        try:
            from apps.flashcards.models import Deck
            total_flashcard_sets = Deck.objects.filter(user=user).count()
        except Exception:
            pass

        feedback_stats = QuizExperienceRating.objects.aggregate(
            total=dm.Count('id'),
            average=dm.Avg('rating'),
        )

        from apps.quiz.models import TopicPerformance
        weak_qs = TopicPerformance.objects.filter(
            user=user, total_questions__gte=3
        ).order_by('accuracy')[:3]
        weak_areas = [{
            'topic':           tp.topic,
            'accuracy':        round(tp.accuracy, 1),
            'total_questions': tp.total_questions,
        } for tp in weak_qs]

        from apps.clash.models import ClashParticipant, ClashRoom
        clash_agg = ClashParticipant.objects.filter(
            user=user, room__status=ClashRoom.FINISHED
        ).aggregate(
            total=dm.Count('id'),
            wins=dm.Count('id', filter=dm.Q(rank=1)),
            best_rank=dm.Min('rank'),
        )

        result = {
            'total_quizzes': quiz_stats['total'] or 0,
            'average_score': round(float(quiz_stats['avg'] or 0), 1),
            'total_flashcard_sets': total_flashcard_sets,
            'total_chats': ChatSession.objects.filter(user=user).count(),
            'study_streak': _calculate_streak(user),
            'total_ratings': int(feedback_stats.get('total') or 0),
            'average_experience_rating': round(float(feedback_stats.get('average') or 0), 2),
            'weak_areas': weak_areas,
            'total_clashes': int(clash_agg['total'] or 0),
            'clash_wins': int(clash_agg['wins'] or 0),
            'best_rank': clash_agg['best_rank'],
        }
        cache.set(cache_key, result, timeout=60)
        return Response(result)


class AdminDashboardStatsView(APIView):
    """GET /api/dashboard/admin/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        cached = cache.get('admin:stats')
        if cached is not None:
            return Response(cached)

        from apps.accounts.models import User
        from apps.flashcards.models import Deck, Flashcard
        from apps.materials.models import Material
        from apps.clash.models import ClashRoom, ClashParticipant

        now = timezone.now()
        day_ago = now - datetime.timedelta(days=1)
        AnonymousUsageEvent.purge_expired(hours=24)

        quiz_stats = QuizSession.objects.aggregate(
            total=dm.Count('id'),
            avg=dm.Avg('score_percentage'),
            total_questions=Coalesce(dm.Sum('total_questions'), Value(0)),
        )

        total_users = User.objects.count()
        verified_users = User.objects.filter(is_email_verified=True).count()
        total_flashcard_decks = Deck.objects.count()
        total_flashcards = Flashcard.objects.count()
        total_chat_sessions = ChatSession.objects.exclude(user__isnull=True).count()
        total_chat_messages = ChatMessage.objects.count()
        total_materials = Material.objects.count()

        feedback_stats = QuizExperienceRating.objects.aggregate(
            total=dm.Count('id'),
            average=dm.Avg('rating'),
        )

        recent_ratings = [
            {
                'rating': row.rating,
                'source': row.source,
                'created_at': row.created_at.isoformat(),
                'actor': row.user.email if row.user else 'Anonymous',
                'is_authenticated': bool(row.user_id),
            }
            for row in QuizExperienceRating.objects.select_related('user').order_by('-created_at')[:20]
        ]

        # Clash stats
        total_clashes = ClashRoom.objects.filter(status=ClashRoom.FINISHED).count()
        clashes_24h = ClashRoom.objects.filter(
            status=ClashRoom.FINISHED, finished_at__gte=day_ago
        ).count()

        clash_questions_chars = _safe_char_sum(
            ClashRoom.objects.filter(status=ClashRoom.FINISHED),
            Length(Cast('questions', output_field=TextField()))
        )
        estimated_tokens_clash = _tokens_from_chars(clash_questions_chars)

        # 24h activity
        quizzes_24h = QuizSession.objects.filter(created_at__gte=day_ago).count()
        decks_24h = Deck.objects.filter(created_at__gte=day_ago).count()
        cards_24h = Flashcard.objects.filter(created_at__gte=day_ago).count()
        chat_messages_24h = ChatMessage.objects.filter(created_at__gte=day_ago).count()
        new_users_24h = User.objects.filter(date_joined__gte=day_ago).count()
        materials_24h = Material.objects.filter(created_at__gte=day_ago).count()
        anonymous_usage_24h = AnonymousUsageEvent.objects.filter(created_at__gte=day_ago).count()

        anonymous_qs = AnonymousUsageEvent.objects.filter(created_at__gte=day_ago)
        anonymous_quiz_24h = anonymous_qs.filter(path__icontains='/quiz/').count()
        anonymous_chat_24h = anonymous_qs.filter(
            dm.Q(path__icontains='/chat/') | dm.Q(path__icontains='/chatbot/')
        ).count()
        anonymous_flashcards_24h = anonymous_qs.filter(path__icontains='/flashcards/').count()
        anonymous_chars_24h = anonymous_qs.aggregate(
            total=Coalesce(dm.Sum('request_chars'), Value(0)) + Coalesce(dm.Sum('response_chars'), Value(0))
        ).get('total') or 0
        anonymous_tokens_24h = _tokens_from_chars(int(anonymous_chars_24h))

        # Character volume for token estimates
        chat_chars = _safe_char_sum(ChatMessage.objects.all(), Length('content'))

        flashcard_q_chars = _safe_char_sum(Flashcard.objects.all(), Length('question'))
        flashcard_a_chars = _safe_char_sum(Flashcard.objects.all(), Length('answer'))
        flashcard_chars = flashcard_q_chars + flashcard_a_chars

        quiz_subject_chars = _safe_char_sum(QuizSession.objects.all(), Length('subject'))
        quiz_questions_json_chars = _safe_char_sum(
            QuizSession.objects.all(),
            Length(Cast('questions_data', output_field=TextField()))
        )
        quiz_answers_json_chars = _safe_char_sum(
            QuizSession.objects.all(),
            Length(Cast('user_answers', output_field=TextField()))
        )
        quiz_chars = quiz_subject_chars + quiz_questions_json_chars + quiz_answers_json_chars

        estimated_tokens_chat = _tokens_from_chars(chat_chars)
        estimated_tokens_flashcards = _tokens_from_chars(flashcard_chars)
        estimated_tokens_quiz = _tokens_from_chars(quiz_chars)
        estimated_tokens_total = (
            estimated_tokens_chat +
            estimated_tokens_flashcards +
            estimated_tokens_quiz +
            estimated_tokens_clash
        )

        avg_quizzes_per_user = round((quiz_stats['total'] or 0) / max(total_users, 1), 2)
        avg_chats_per_user = round(total_chat_sessions / max(total_users, 1), 2)

        # Estimated cost
        estimated_cost_usd = _cost_from_tokens(estimated_tokens_total)

        # Average AI response latency (7-day rolling window)
        week_ago = timezone.now() - datetime.timedelta(days=7)
        latency_agg = AIResponseLatency.objects.filter(created_at__gte=week_ago).aggregate(
            avg_ms=dm.Avg('duration_ms'),
            sample_count=dm.Count('id'),
        )
        avg_response_ms = round(float(latency_agg['avg_ms'] or 0), 1)
        latency_sample_count = int(latency_agg['sample_count'] or 0)

        # Last-24h activity feed for dashboard overview only
        recent_activity_payload, _, _ = _collect_admin_activity(start_at=day_ago, limit=20, offset=0)

        result = {
            'total_users': total_users,
            'verified_users': verified_users,
            'total_quizzes': quiz_stats['total'] or 0,
            'total_quiz_questions': int(quiz_stats['total_questions'] or 0),
            'total_materials': total_materials,
            'total_flashcard_decks': total_flashcard_decks,
            'total_flashcards': total_flashcards,
            'total_chat_sessions': total_chat_sessions,
            'total_chat_messages': total_chat_messages,
            'total_clashes': total_clashes,
            'average_score': round(float(quiz_stats['avg'] or 0), 1),
            'total_ratings': int(feedback_stats.get('total') or 0),
            'average_experience_rating': round(float(feedback_stats.get('average') or 0), 2),
            'recent_ratings': recent_ratings,
            'avg_quizzes_per_user': avg_quizzes_per_user,
            'avg_chats_per_user': avg_chats_per_user,
            'activity_24h': {
                'new_users': new_users_24h,
                'quizzes': quizzes_24h,
                'decks': decks_24h,
                'flashcards': cards_24h,
                'chat_messages': chat_messages_24h,
                'uploaded_materials': materials_24h,
                'clashes': clashes_24h,
                'anonymous_api_hits': anonymous_usage_24h,
            },
            'unauthenticated_usage_24h': {
                'quiz_requests': anonymous_quiz_24h,
                'chat_requests': anonymous_chat_24h,
                'flashcard_requests': anonymous_flashcards_24h,
                'estimated_tokens': anonymous_tokens_24h,
                'source': 'anonymous_api_events',
                'retention_hours': 24,
            },
            'recent_activity': recent_activity_payload,
            'estimated_tokens': {
                'chat': estimated_tokens_chat,
                'quiz': estimated_tokens_quiz,
                'flashcards': estimated_tokens_flashcards,
                'clash': estimated_tokens_clash,
                'total': estimated_tokens_total,
                'estimated_cost_usd': estimated_cost_usd,
                'method': 'chars_div_4_estimate',
                'note': 'Approximation only. Provider billing tokens may differ.',
            },
            'avg_response_ms': avg_response_ms,
            'latency_sample_count': latency_sample_count,
        }
        cache.set('admin:stats', result, timeout=120)
        return Response(result)


class AdminUsageTrendsView(APIView):
    """GET /api/dashboard/admin/usage-trends/?days=14"""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):

        from apps.accounts.models import User
        from apps.flashcards.models import Deck
        from apps.materials.models import Material
        from apps.clash.models import ClashRoom

        try:
            days = int(request.query_params.get("days", 14))
        except (TypeError, ValueError):
            days = 14
        days = max(7, min(days, 90))

        cache_key = f'admin:trends:{days}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        today = timezone.now().date()
        start_day = today - datetime.timedelta(days=days - 1)

        def _series(qs, date_field: str):
            rows = (
                qs.filter(**{f"{date_field}__date__gte": start_day})
                .annotate(day=TruncDate(date_field))
                .values("day")
                .annotate(count=dm.Count("id"))
                .order_by("day")
            )
            return {r["day"]: int(r["count"]) for r in rows}

        users_map = _series(User.objects.all(), "date_joined")
        quizzes_map = _series(QuizSession.objects.all(), "created_at")
        decks_map = _series(Deck.objects.all(), "created_at")
        chats_map = _series(ChatMessage.objects.all(), "created_at")
        materials_map = _series(Material.objects.all(), "created_at")
        clashes_map = _series(
            ClashRoom.objects.filter(status=ClashRoom.FINISHED), "finished_at"
        )

        labels = []
        users = []
        quizzes = []
        decks = []
        chats = []
        materials = []
        clashes = []
        for offset in range(days):
            day = start_day + datetime.timedelta(days=offset)
            labels.append(day.isoformat())
            users.append(users_map.get(day, 0))
            quizzes.append(quizzes_map.get(day, 0))
            decks.append(decks_map.get(day, 0))
            chats.append(chats_map.get(day, 0))
            materials.append(materials_map.get(day, 0))
            clashes.append(clashes_map.get(day, 0))

        result = {
            "days": days,
            "labels": labels,
            "series": {
                "new_users": users,
                "quizzes": quizzes,
                "decks": decks,
                "chat_messages": chats,
                "uploaded_materials": materials,
                "clashes": clashes,
            },
        }
        cache.set(cache_key, result, timeout=120)
        return Response(result)


class AdminAnonymousUsageView(APIView):
    """GET /api/dashboard/admin/anonymous-usage/?limit=200"""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", 200))
        except (TypeError, ValueError):
            limit = 200
        limit = max(1, min(limit, 500))

        deleted_count = AnonymousUsageEvent.purge_expired(hours=24)
        start_at = timezone.now() - datetime.timedelta(hours=24)

        queryset = AnonymousUsageEvent.objects.filter(created_at__gte=start_at)

        rows = list(queryset.order_by("-created_at")[:limit])
        events = [
            {
                "id": row.id,
                "created_at": row.created_at.isoformat(),
                "method": row.method,
                "path": row.path,
                "query_string": row.query_string,
                "status_code": row.status_code,
                "request_chars": row.request_chars,
                "response_chars": row.response_chars,
                "tutor_message": row.tutor_message,
                "tutor_response": row.tutor_response,
                "session_key": row.session_key,
                "ip_address": row.ip_address,
                "user_agent": row.user_agent,
            }
            for row in rows
        ]

        totals = queryset.aggregate(
            total=dm.Count("id"),
            unique_sessions=dm.Count("session_key", distinct=True),
        )

        top_paths = list(
            queryset.values("path")
            .annotate(count=dm.Count("id"))
            .order_by("-count", "path")[:20]
        )

        by_status = list(
            queryset.values("status_code")
            .annotate(count=dm.Count("id"))
            .order_by("status_code")
        )

        return Response(
            {
                "retention_hours": 24,
                "deleted_expired": int(deleted_count or 0),
                "total_last_24h": int(totals.get("total") or 0),
                "unique_sessions_last_24h": int(totals.get("unique_sessions") or 0),
                "top_paths": top_paths,
                "by_status": by_status,
                "events": events,
            }
        )


class AdminActivityFeedView(APIView):
    """GET /api/dashboard/admin/activity/?period=day|week|month|quarter|year|all&limit=50&offset=0"""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):

        period = (request.query_params.get("period") or "day").strip().lower()

        custom_days_raw = request.query_params.get("custom_days")
        custom_days = None
        if custom_days_raw is not None:
            try:
                custom_days = max(1, min(int(custom_days_raw), 365))
            except (TypeError, ValueError):
                custom_days = None

        period_days_map = {
            "day": 1,
            "week": 7,
            "month": 30,
            "quarter": 90,
            "year": 365,
            "all": None,
        }

        if custom_days is not None:
            days = custom_days
            resolved_period = f"custom_{custom_days}_days"
        else:
            days = period_days_map.get(period, 1)
            resolved_period = period if period in period_days_map else "day"

        try:
            limit = int(request.query_params.get("limit", 50))
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 200))

        try:
            offset = int(request.query_params.get("offset", 0))
        except (TypeError, ValueError):
            offset = 0
        offset = max(0, offset)

        start_at = None if days is None else timezone.now() - datetime.timedelta(days=days)

        activities, total_count, counts_by_type = _collect_admin_activity(
            start_at=start_at,
            limit=limit,
            offset=offset,
        )

        return Response(
            {
                "period": resolved_period,
                "days": days,
                "limit": limit,
                "offset": offset,
                "total": total_count,
                "has_more": (offset + len(activities)) < total_count,
                "counts": counts_by_type,
                "activities": activities,
            }
        )


class AdminUsersListView(APIView):
    """GET /api/dashboard/admin/users/ - paginated list of users"""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        from apps.accounts.models import User
        from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

        # Pagination params
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 50)
        
        try:
            page = int(page)
            page_size = min(int(page_size), 200)  # Max 200 per page
        except (ValueError, TypeError):
            page = 1
            page_size = 50

        # Use a safe Subquery for chat count so we don't depend on
        # the ChatSession.user related_name being 'chatsession'.
        chat_count_sq = (
            ChatSession.objects
            .filter(user=dm.OuterRef('pk'))
            .values('user')
            .annotate(c=dm.Count('id'))
            .values('c')
        )
        
        all_users = (
            User.objects
            .annotate(
                total_quizzes=dm.Count('quiz_sessions', distinct=True),
                total_flashcard_sets=dm.Count('decks', distinct=True),
                total_chats=Coalesce(dm.Subquery(chat_count_sq), Value(0)),
            )
            .order_by('-date_joined')
        )
        
        paginator = Paginator(all_users, page_size)
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)
        
        data = []
        for u in page_obj:
            d = user_to_dict(u)
            d['total_quizzes'] = int(getattr(u, 'total_quizzes', 0) or 0)
            d['total_flashcard_sets'] = int(getattr(u, 'total_flashcard_sets', 0) or 0)
            d['total_chats'] = int(getattr(u, 'total_chats', 0) or 0)
            d['date_joined'] = u.date_joined.strftime('%b %d, %Y')
            data.append(d)

        return Response({'users': data})


class AdminUserDeleteView(APIView):
    """DELETE /api/dashboard/admin/users/<user_id>/ - get user details and delete"""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, user_id):

        from apps.accounts.models import User
        from apps.flashcards.models import Deck, Flashcard
        from apps.materials.models import Material
        from apps.clash.models import ClashRoom, ClashParticipant

        try:
            target = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=404)

        quizzes_qs = QuizSession.objects.filter(user=target)
        decks_qs = Deck.objects.filter(user=target)
        flashcards_qs = Flashcard.objects.filter(deck__user=target)
        chat_sessions_qs = ChatSession.objects.filter(user=target)
        chat_messages_qs = ChatMessage.objects.filter(session__user=target)
        materials_qs = Material.objects.filter(uploaded_by=target)
        clash_parts_qs = ClashParticipant.objects.filter(
            user=target, room__status=ClashRoom.FINISHED
        ).select_related('room')

        quiz_count = quizzes_qs.count()
        flashcard_decks_count = decks_qs.count()
        flashcards_count = flashcards_qs.count()
        chat_sessions_count = chat_sessions_qs.count()
        chat_messages_count = chat_messages_qs.count()

        quiz_chars = (
            _safe_char_sum(quizzes_qs, Length('subject')) +
            _safe_char_sum(quizzes_qs, Length(Cast('questions_data', output_field=TextField()))) +
            _safe_char_sum(quizzes_qs, Length(Cast('user_answers', output_field=TextField())))
        )
        flashcard_chars = (
            _safe_char_sum(flashcards_qs, Length('question')) +
            _safe_char_sum(flashcards_qs, Length('answer'))
        )
        chat_chars = _safe_char_sum(chat_messages_qs, Length('content'))

        tokens_quiz = _tokens_from_chars(quiz_chars)
        tokens_flashcards = _tokens_from_chars(flashcard_chars)
        tokens_chat = _tokens_from_chars(chat_chars)

        # Clash stats
        total_clashes = clash_parts_qs.count()
        clashes_as_host = clash_parts_qs.filter(is_host=True).count()
        clash_wins = clash_parts_qs.filter(rank=1).count()
        clash_avg_score = clash_parts_qs.aggregate(avg=dm.Avg('score'))['avg'] or 0

        # Clash token estimate — only rooms this user hosted (host pays for question generation)
        hosted_room_ids = list(clash_parts_qs.filter(is_host=True).values_list('room_id', flat=True))
        clash_chars = _safe_char_sum(
            ClashRoom.objects.filter(id__in=hosted_room_ids),
            Length(Cast('questions', output_field=TextField()))
        )
        tokens_clash = _tokens_from_chars(clash_chars)

        quiz_stats = quizzes_qs.aggregate(
            avg=dm.Avg('score_percentage'),
            total_questions=Coalesce(dm.Sum('total_questions'), Value(0)),
        )

        # Get user's quiz experience rating
        user_rating = QuizExperienceRating.objects.filter(user=target).order_by('-updated_at').first()
        user_rating_value = user_rating.rating if user_rating else None

        # Recent per-user activity (quizzes + flashcards + chat)
        recent_activity = []
        for q in quizzes_qs.order_by('-created_at')[:10]:
            recent_activity.append({
                "type": "quiz",
                "text": f"completed a {(q.subject or 'General')} quiz ({q.score_percentage}%)",
                "created_at": q.created_at,
            })

        for d in decks_qs.order_by('-created_at')[:10]:
            recent_activity.append({
                "type": "flashcards",
                "text": f"created flashcard deck '{d.title}'",
                "created_at": d.created_at,
            })

        for s in chat_sessions_qs.order_by('-created_at')[:10]:
            msg_count = ChatMessage.objects.filter(session=s).count()
            recent_activity.append({
                "type": "chat",
                "text": f"chat session ({msg_count} message{'s' if msg_count != 1 else ''})",
                "created_at": s.created_at,
            })

        for p in clash_parts_qs.order_by('-room__finished_at')[:10]:
            role = 'hosted' if p.is_host else 'played'
            player_count = ClashParticipant.objects.filter(room=p.room).count()
            recent_activity.append({
                "type": "clash",
                "text": f"{role} a Clash on '{p.room.subject}' — #{p.rank} of {player_count} ({p.score} pts)",
                "created_at": p.room.finished_at,
            })

        recent_activity.sort(key=lambda item: item["created_at"], reverse=True)
        recent_activity = [
            {**item, "created_at": item["created_at"].isoformat()}
            for item in recent_activity[:20]
        ]

        tokens_total = tokens_quiz + tokens_flashcards + tokens_chat + tokens_clash
        return Response({
            'user': user_to_dict(target),
            'summary': {
                'total_quizzes': quiz_count,
                'total_quiz_questions': int(quiz_stats.get('total_questions') or 0),
                'average_score': round(float(quiz_stats.get('avg') or 0), 1),
                'total_flashcard_decks': flashcard_decks_count,
                'total_flashcards': flashcards_count,
                'total_chat_sessions': chat_sessions_count,
                'total_chat_messages': chat_messages_count,
                'total_materials': materials_qs.count(),
                'total_clashes': total_clashes,
                'clashes_as_host': clashes_as_host,
                'clash_wins': clash_wins,
                'clash_avg_score': int(round(float(clash_avg_score))),
                'user_rating': user_rating_value,
            },
            'estimated_tokens': {
                'quiz': tokens_quiz,
                'flashcards': tokens_flashcards,
                'chat': tokens_chat,
                'clash': tokens_clash,
                'total': tokens_total,
                'estimated_cost_usd': _cost_from_tokens(tokens_total),
                'method': 'chars_div_4_estimate',
            },
            'recent_activity': recent_activity,
        })

    def delete(self, request, user_id):
        from apps.accounts.models import User
        try:
            target = User.objects.get(id=user_id)
            if target.is_admin:
                return Response({'detail': 'Cannot delete an admin.'}, status=400)
            
            # Audit log the deletion
            logger.warning("AUDIT: Admin %s deleted user %s (%s) at %s", 
                          request.user.email, target.id, target.email, timezone.now())
            
            target.delete()
            return Response({'detail': f'User {target.username} removed.'})
        except User.DoesNotExist:
            return Response({'detail': f'User {target.username} not found.'}, status=404)


class ContactMessageView(APIView):
    """POST /api/dashboard/contact/"""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ContactThrottle]

    def post(self, request):
        serializer = ContactFormSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            send_contact_emails(**serializer.validated_data)
        except (EmailDeliveryError, ValueError) as exc:
            logger.exception("Contact email delivery failed: %s", exc)
            return Response(
                {"detail": "Message saved but email delivery is temporarily unavailable."},
                status=202,
            )

        return Response({"detail": "Message sent successfully."})


class NewsletterSubscribeView(APIView):
    """POST /api/dashboard/newsletter/"""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ContactThrottle]

    def post(self, request):
        serializer = NewsletterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            send_newsletter_emails(serializer.validated_data["email"])
        except (EmailDeliveryError, ValueError) as exc:
            logger.exception("Newsletter email delivery failed: %s", exc)
            return Response(
                {"detail": "Subscription received but email delivery is temporarily unavailable."},
                status=202,
            )

        return Response({"detail": "Subscription successful."})


class QuizFeedbackView(APIView):
    """GET/POST /api/dashboard/quiz-feedback/"""
    permission_classes = [AllowAny]

    def _resolve_source(self, value: str) -> str:
        allowed = {"quiz_results"}
        normalized = (value or "quiz_results").strip().lower()
        return normalized if normalized in allowed else "quiz_results"

    def _resolve_session_key(self, request) -> str:
        if not request.session.session_key:
            request.session.save()
        return request.session.session_key or ""

    def get(self, request):
        source = self._resolve_source(request.query_params.get("source"))

        aggregate = QuizExperienceRating.objects.filter(source=source).aggregate(
            total=dm.Count('id'),
            average=dm.Avg('rating'),
        )

        current = None
        if request.user and request.user.is_authenticated:
            current = QuizExperienceRating.objects.filter(user=request.user, source=source).order_by('-updated_at').first()
        else:
            session_key = self._resolve_session_key(request)
            current = QuizExperienceRating.objects.filter(user__isnull=True, session_key=session_key, source=source).order_by('-updated_at').first()

        return Response({
            'source': source,
            'total_ratings': int(aggregate.get('total') or 0),
            'average_rating': round(float(aggregate.get('average') or 0), 2),
            'user_rating': int(current.rating) if current else None,
        })

    def post(self, request):
        serializer = QuizFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        source = self._resolve_source(serializer.validated_data.get('source'))
        rating_value = serializer.validated_data['rating']
        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')
        ua = (request.META.get('HTTP_USER_AGENT') or '')[:255]

        if request.user and request.user.is_authenticated:
            rating_obj, _ = QuizExperienceRating.objects.update_or_create(
                user=request.user,
                source=source,
                defaults={
                    'rating': rating_value,
                    'session_key': self._resolve_session_key(request),
                    'ip_address': ip,
                    'user_agent': ua,
                },
            )
        else:
            session_key = self._resolve_session_key(request)
            rating_obj = QuizExperienceRating.objects.filter(
                user__isnull=True,
                session_key=session_key,
                source=source,
            ).order_by('-updated_at').first()

            if rating_obj:
                rating_obj.rating = rating_value
                rating_obj.ip_address = ip
                rating_obj.user_agent = ua
                rating_obj.save(update_fields=['rating', 'ip_address', 'user_agent', 'updated_at'])
            else:
                rating_obj = QuizExperienceRating.objects.create(
                    user=None,
                    session_key=session_key,
                    source=source,
                    rating=rating_value,
                    ip_address=ip,
                    user_agent=ua,
                )

        aggregate = QuizExperienceRating.objects.filter(source=source).aggregate(
            total=dm.Count('id'),
            average=dm.Avg('rating'),
        )

        return Response({
            'detail': 'Feedback saved.',
            'rating': int(rating_obj.rating),
            'source': source,
            'total_ratings': int(aggregate.get('total') or 0),
            'average_rating': round(float(aggregate.get('average') or 0), 2),
        })


class AdminQuizFeedbackListView(APIView):
    """GET /api/dashboard/admin/quiz-feedback/"""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            limit = int(request.query_params.get('limit', 100))
        except (TypeError, ValueError):
            limit = 100
        limit = max(1, min(limit, 200))

        source = (request.query_params.get('source') or 'quiz_results').strip().lower()

        queryset = QuizExperienceRating.objects.select_related('user').order_by('-created_at')
        if source:
            queryset = queryset.filter(source=source)

        rows = list(queryset[:limit])

        payload = [
            {
                'id': row.id,
                'rating': row.rating,
                'source': row.source,
                'created_at': row.created_at.isoformat(),
                'actor': row.user.email if row.user else 'Anonymous',
                'is_authenticated': bool(row.user_id),
            }
            for row in rows
        ]

        stats = queryset.aggregate(total=dm.Count('id'), average=dm.Avg('rating'))

        return Response({
            'ratings': payload,
            'total': int(stats.get('total') or 0),
            'average_rating': round(float(stats.get('average') or 0), 2),
        })


class IsAdminUser(BasePermission):
    """Permission class to check if user is an admin."""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and getattr(request.user, 'is_admin', False)


class AdminSystemSettingsView(APIView):
    """GET/PUT /api/dashboard/admin/settings/
    
    Manage system-wide settings accessible only to admin users.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        """Get current system settings."""
        from .settings_model import SystemSettings
        from .settings_serializers import SystemSettingsSerializer
        
        settings = SystemSettings.get_instance()
        serializer = SystemSettingsSerializer(settings)
        return Response(serializer.data)
    
    def put(self, request):
        """Update system settings."""
        from .settings_model import SystemSettings
        from .settings_serializers import SystemSettingsSerializer
        
        settings = SystemSettings.get_instance()
        serializer = SystemSettingsSerializer(settings, data=request.data, partial=True)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Track who made the update
        serializer.validated_data['updated_by'] = request.user
        serializer.save()
        
        return Response({
            "detail": "Settings updated successfully.",
            "data": serializer.data
        })