import django.db.models.deletion
from django.db import migrations, models
from pgvector.django import HnswIndex, VectorExtension, VectorField


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        VectorExtension(),
        migrations.CreateModel(
            name="TutorDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_key", models.CharField(max_length=255, unique=True)),
                ("source_name", models.CharField(max_length=255)),
                ("file_type", models.CharField(max_length=12)),
                ("content_sha256", models.CharField(max_length=64)),
                ("index_version", models.CharField(max_length=100)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("indexed_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["source_name"]},
        ),
        migrations.CreateModel(
            name="TutorDocumentChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chunk_index", models.PositiveIntegerField()),
                ("page_number", models.PositiveIntegerField(blank=True, null=True)),
                ("content", models.TextField()),
                ("embedding", VectorField(dimensions=1536)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chunks", to="tutor.tutordocument")),
            ],
            options={
                "ordering": ["document_id", "chunk_index"],
                "indexes": [
                    HnswIndex(
                        ef_construction=64,
                        fields=["embedding"],
                        m=16,
                        name="tutor_doc_embedding_hnsw",
                        opclasses=["vector_cosine_ops"],
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("document", "chunk_index"), name="tutor_doc_chunk_index_uniq"),
                ],
            },
        ),
    ]
