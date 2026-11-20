from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ChatbotDataMigrationTests(TransactionTestCase):
    """Verify migration copies every legacy chatbot table without deleting it."""

    migrate_from = [
        ("chatbot", "0004_chatsession_has_document"),
        ("tutor", "0001_pgvector_documents"),
    ]
    migrate_to = [("tutor", "0002_migrate_chatbot_data")]

    def tearDown(self):
        # Leave the test database at the latest project schema for other tests.
        MigrationExecutor(connection).migrate(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        )
        super().tearDown()

    def test_copies_chatbot_records_and_preserves_the_sources(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        old_knowledge = old_apps.get_model("chatbot", "ChatbotKnowledge")
        old_session = old_apps.get_model("chatbot", "ChatSession")
        old_message = old_apps.get_model("chatbot", "ChatMessage")
        old_cache = old_apps.get_model("chatbot", "ResearchCache")

        knowledge = old_knowledge.objects.create(
            category="platform",
            question="How do tutors work?",
            answer="They help learners.",
            keywords="tutor,learning",
            is_active=True,
        )
        session = old_session.objects.create(
            session_id="legacy-session-1",
            title="Legacy conversation",
            has_document=True,
        )
        message = old_message.objects.create(
            session_id=session.pk,
            sender="user",
            content="Explain this document.",
        )
        cache_entry = old_cache.objects.create(
            query="legacy research query",
            result="legacy research result",
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        new_apps = executor.loader.project_state(self.migrate_to).apps

        self.assertEqual(
            new_apps.get_model("tutor", "TutorKnowledge").objects.get(pk=knowledge.pk).answer,
            knowledge.answer,
        )
        self.assertEqual(
            new_apps.get_model("tutor", "TutorKnowledge").objects.get(pk=knowledge.pk).created_at,
            knowledge.created_at,
        )
        new_session = new_apps.get_model("tutor", "TutorSession").objects.get(pk=session.pk)
        self.assertEqual(new_session.session_id, session.session_id)
        self.assertEqual(new_session.title, session.title)
        self.assertEqual(
            new_apps.get_model("tutor", "TutorMessage").objects.get(pk=message.pk).content,
            message.content,
        )
        self.assertEqual(
            new_apps.get_model("tutor", "TutorResearchCache").objects.get(pk=cache_entry.pk).result,
            cache_entry.result,
        )

        # The chatbot tables remain intact until the old app is explicitly retired.
        current_apps = MigrationExecutor(connection).loader.project_state(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        ).apps
        self.assertTrue(current_apps.get_model("chatbot", "ChatSession").objects.filter(pk=session.pk).exists())
        self.assertTrue(current_apps.get_model("chatbot", "ChatMessage").objects.filter(pk=message.pk).exists())
        self.assertTrue(current_apps.get_model("chatbot", "ChatbotKnowledge").objects.filter(pk=knowledge.pk).exists())
        self.assertTrue(current_apps.get_model("chatbot", "ResearchCache").objects.filter(pk=cache_entry.pk).exists())
