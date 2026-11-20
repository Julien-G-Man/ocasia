from django.conf import settings
from django.core.management.color import no_style
from django.db import migrations, models
import django.utils.timezone
import django.db.models.deletion
from itertools import islice


def bulk_copy(queryset, target_model, convert_row, batch_size=1000):
    iterator = queryset.iterator(chunk_size=batch_size)
    while rows := list(islice(iterator, batch_size)):
        target_model.objects.bulk_create(
            [convert_row(row) for row in rows],
            batch_size=batch_size,
        )


def copy_chatbot_data(apps, schema_editor):
    """Copy chatbot records into tutor tables and leave chatbot data untouched."""
    ChatbotKnowledge = apps.get_model("chatbot", "ChatbotKnowledge")
    ChatSession = apps.get_model("chatbot", "ChatSession")
    ChatMessage = apps.get_model("chatbot", "ChatMessage")
    ResearchCache = apps.get_model("chatbot", "ResearchCache")

    TutorKnowledge = apps.get_model("tutor", "TutorKnowledge")
    TutorSession = apps.get_model("tutor", "TutorSession")
    TutorMessage = apps.get_model("tutor", "TutorMessage")
    TutorResearchCache = apps.get_model("tutor", "TutorResearchCache")

    # These tables are new, so preserving primary keys provides a clear
    # one-to-one correspondence while keeping sessions and messages linked.
    bulk_copy(
        ChatbotKnowledge.objects.all().order_by("pk"),
        TutorKnowledge,
        lambda row: TutorKnowledge(
            id=row.pk,
            category=row.category,
            question=row.question,
            answer=row.answer,
            keywords=row.keywords,
            is_active=row.is_active,
            created_at=row.created_at,
        ),
    )

    bulk_copy(
        ChatSession.objects.all().order_by("pk"),
        TutorSession,
        lambda row: TutorSession(
            id=row.pk,
            user_id=row.user_id,
            session_id=row.session_id,
            title=row.title,
            has_document=row.has_document,
            created_at=row.created_at,
        ),
    )

    bulk_copy(
        ChatMessage.objects.all().order_by("pk"),
        TutorMessage,
        lambda row: TutorMessage(
            id=row.pk,
            session_id=row.session_id,
            sender=row.sender,
            content=row.content,
            created_at=row.created_at,
        ),
    )

    bulk_copy(
        ResearchCache.objects.all().order_by("pk"),
        TutorResearchCache,
        lambda row: TutorResearchCache(
            id=row.pk,
            query=row.query,
            result=row.result,
            created_at=row.created_at,
        ),
    )

    # Explicitly copied primary keys require advancing the new sequences.
    connection = schema_editor.connection
    models_to_reset = [TutorKnowledge, TutorSession, TutorMessage, TutorResearchCache]
    with connection.cursor() as cursor:
        for sql in connection.ops.sequence_reset_sql(no_style(), models_to_reset):
            cursor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("chatbot", "0004_chatsession_has_document"),
        ("tutor", "0001_pgvector_documents"),
    ]

    operations = [
        migrations.CreateModel(
            name="TutorKnowledge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(max_length=50)),
                ("question", models.CharField(max_length=200)),
                ("answer", models.TextField()),
                ("keywords", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
            ],
        ),
        migrations.CreateModel(
            name="TutorResearchCache",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("query", models.CharField(max_length=255, unique=True)),
                ("result", models.TextField()),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
            ],
        ),
        migrations.CreateModel(
            name="TutorSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_id", models.CharField(max_length=100, unique=True)),
                ("title", models.CharField(blank=True, default="", max_length=120)),
                ("has_document", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user", "-created_at"], name="tutor_session_user_created_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="TutorMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sender", models.CharField(choices=[("user", "User"), ("ai", "AI")], max_length=10)),
                ("content", models.TextField()),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="tutor.tutorsession")),
            ],
            options={
                "ordering": ["created_at"],
                "indexes": [
                    models.Index(fields=["session", "created_at"], name="tutor_msg_session_created_idx"),
                ],
            },
        ),
        migrations.RunPython(copy_chatbot_data, migrations.RunPython.noop),
    ]
