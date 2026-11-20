from django.conf import settings
from django.db import models
from django.utils import timezone
from pgvector.django import HnswIndex, VectorField


TUTOR_MESSAGE_TYPES = (
    ("user", "User"),
    ("ai", "AI"),
)


class TutorKnowledge(models.Model):
    """Curated knowledge retained from the legacy chatbot knowledge table."""

    category = models.CharField(max_length=50)
    question = models.CharField(max_length=200)
    answer = models.TextField()
    keywords = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return self.question[:50]


class TutorResearchCache(models.Model):
    """Cached research results retained during the chatbot retirement period."""

    query = models.CharField(max_length=255, unique=True)
    result = models.TextField()
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return self.query


class TutorSession(models.Model):
    """Tutor conversation session; mirrors legacy chat data during cutover."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    session_id = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=120, blank=True, default="")
    has_document = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        indexes = [
            models.Index(fields=["user", "-created_at"], name="tutor_session_user_created_idx"),
        ]

    def __str__(self):
        return self.title or self.session_id


class TutorMessage(models.Model):
    """A message in a tutor session."""

    session = models.ForeignKey(
        TutorSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.CharField(max_length=10, choices=TUTOR_MESSAGE_TYPES)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["session", "created_at"], name="tutor_msg_session_created_idx"),
        ]

    def __str__(self):
        return f"{self.sender}: {self.content[:40]}"


class TutorDocument(models.Model):
    """A source file indexed for retrieval by the tutor."""

    source_key = models.CharField(max_length=255, unique=True)
    source_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=12)
    content_sha256 = models.CharField(max_length=64)
    index_version = models.CharField(max_length=100)
    metadata = models.JSONField(default=dict, blank=True)
    indexed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["source_name"]

    def __str__(self):
        return self.source_name


class TutorDocumentChunk(models.Model):
    """A text chunk and embedding from an indexed tutor document."""

    document = models.ForeignKey(TutorDocument, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.PositiveIntegerField()
    page_number = models.PositiveIntegerField(null=True, blank=True)
    content = models.TextField()
    embedding = VectorField(dimensions=1536)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["document_id", "chunk_index"]
        constraints = [
            models.UniqueConstraint(fields=["document", "chunk_index"], name="tutor_doc_chunk_index_uniq"),
        ]
        indexes = [
            HnswIndex(
                name="tutor_doc_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self):
        return f"{self.document.source_name} chunk {self.chunk_index}"
