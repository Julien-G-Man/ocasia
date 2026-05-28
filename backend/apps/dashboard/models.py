from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .settings_model import SystemSettings


class QuizExperienceRating(models.Model):
    """Stores quiz experience star ratings from authenticated and anonymous users."""

    SOURCE_CHOICES = [
        ("quiz_results", "Quiz Results"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quiz_experience_ratings",
    )
    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    source = models.CharField(max_length=40, choices=SOURCE_CHOICES, default="quiz_results", db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["source", "updated_at"]),
        ]

    def __str__(self):
        actor = self.user.email if self.user else (self.session_key or "anonymous")
        return f"{actor} rated {self.rating}/5"


class AnonymousUsageEvent(models.Model):
    """Ephemeral activity log for unauthenticated API usage (24h retention)."""

    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=255, db_index=True)
    query_string = models.CharField(max_length=255, blank=True)
    status_code = models.PositiveSmallIntegerField(db_index=True)
    request_chars = models.PositiveIntegerField(default=0)
    response_chars = models.PositiveIntegerField(default=0)
    tutor_message = models.TextField(blank=True)
    tutor_response = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["path", "created_at"]),
        ]

    @classmethod
    def purge_expired(cls, hours: int = 24) -> int:
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        deleted, _ = cls.objects.filter(created_at__lt=cutoff).delete()
        return int(deleted)


class AIResponseLatency(models.Model):
    """Per-request AI latency log. Kept for 30 days; used for avg response time stats."""

    CHAT = 'chat'
    QUIZ = 'quiz'
    FLASHCARDS = 'flashcards'
    FEATURE_CHOICES = [
        (CHAT, 'Chat'),
        (QUIZ, 'Quiz'),
        (FLASHCARDS, 'Flashcards'),
    ]

    feature = models.CharField(max_length=20, choices=FEATURE_CHOICES, db_index=True)
    duration_ms = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['feature', 'created_at'])]

    @classmethod
    def purge_old(cls, days: int = 30) -> int:
        cutoff = timezone.now() - timezone.timedelta(days=days)
        deleted, _ = cls.objects.filter(created_at__lt=cutoff).delete()
        return int(deleted)


__all__ = ["SystemSettings", "QuizExperienceRating", "AnonymousUsageEvent", "AIResponseLatency"]
