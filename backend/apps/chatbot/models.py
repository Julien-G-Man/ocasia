from django.conf import settings
from django.db import models

MESSAGE_TYPES = (
    ("user", "User"),
    ("ai", "AI"),
)


class ChatbotKnowledge(models.Model):
    """
    Curated knowledge about Lamla AI used for grounding
    and system-level responses.
    """
    category   = models.CharField(max_length=50)
    question   = models.CharField(max_length=200)
    answer     = models.TextField()
    keywords   = models.TextField(blank=True)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.question[:50]


class ChatSession(models.Model):
    """
    Logical chat session.
    Allows continuity for anonymous users.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    session_id = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=120, blank=True, default="")
    has_document = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "-created_at"], name="chat_session_user_created_idx"),
        ]

    def __str__(self):
        return self.title or self.session_id


class ChatMessage(models.Model):
    """
    Individual chat turns (user / AI).
    """
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender    = models.CharField(max_length=10, choices=MESSAGE_TYPES)
    content   = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["session", "created_at"], name="chat_msg_session_created_idx"),
        ]

    def __str__(self):
        return f"{self.sender}: {self.content[:40]}"


class ResearchCache(models.Model):
    """
    Cache for expensive AI research / reasoning queries.
    """
    query      = models.CharField(max_length=255, unique=True)
    result     = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.query