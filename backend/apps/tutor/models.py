from django.db import models
from pgvector.django import HnswIndex, VectorField


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
