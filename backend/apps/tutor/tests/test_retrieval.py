import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from django.test import SimpleTestCase
from django.apps import apps

from apps.tutor.retrieval import RAGEngine


class RAGEngineTests(SimpleTestCase):
    def test_bm25_ranks_exact_lexical_matches(self):
        documents = [
            {"id": 1, "content": "Photosynthesis uses light energy to make glucose."},
            {"id": 2, "content": "Cellular respiration releases energy from glucose."},
            {"id": 3, "content": "The mitochondrion is an organelle."},
        ]

        results = RAGEngine._bm25("photosynthesis light", documents)

        self.assertEqual(results[0]["id"], 1)
        self.assertEqual(len(results), 1)

    def test_passage_deduplication_ignores_case_and_whitespace(self):
        self.assertEqual(
            RAGEngine._passage_key("  The   Cell\nMembrane "),
            RAGEngine._passage_key("the cell membrane"),
        )

    async def test_search_does_not_index_platform_knowledge(self):
        engine = RAGEngine()
        engine._embeddings = SimpleNamespace(aembed_query=AsyncMock(return_value=[0.1]))
        engine.index_platform_knowledge = Mock()

        def sync_adapter(function, **_kwargs):
            async def call(*args):
                return function(*args)
            return call

        with patch("apps.tutor.retrieval.sync_to_async", side_effect=sync_adapter), patch.object(
            RAGEngine, "_hybrid_search", return_value=[{"text": "matched"}]
        ):
            result = await engine.search("question")

        self.assertEqual(result, [{"text": "matched"}])
        engine.index_platform_knowledge.assert_not_called()

    def test_startup_indexer_indexes_missing_markdown_and_text_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.md").write_text("Platform help document", encoding="utf-8")
            (root / "two.txt").write_text("More platform help document", encoding="utf-8")
            (root / "ignored.json").write_text("{}", encoding="utf-8")
            engine = RAGEngine()
            engine._embeddings = object()

            with patch.dict("os.environ", {"KB_FILE_PATH": directory}), patch(
                "apps.tutor.models.TutorDocument.objects.filter"
            ) as filter_documents, patch(
                "apps.tutor.rag_indexing.index_document_bytes", return_value=(True, 1)
            ) as index_document:
                filter_documents.return_value.only.return_value.first.return_value = None
                count = engine.index_platform_knowledge()

        self.assertEqual(count, 2)
        self.assertEqual(index_document.call_count, 2)


class StartupIndexingTests(SimpleTestCase):
    @patch("apps.tutor.retrieval.rag_engine.index_platform_knowledge")
    def test_web_worker_indexes_platform_knowledge_at_startup(self, index_knowledge):
        config = apps.get_app_config("tutor")
        with patch("apps.tutor.apps.sys.argv", ["gunicorn", "config.asgi:application"]):
            config.ready()
        index_knowledge.assert_called_once_with()

    @patch("apps.tutor.retrieval.rag_engine.index_platform_knowledge")
    def test_management_commands_do_not_index_platform_knowledge(self, index_knowledge):
        config = apps.get_app_config("tutor")
        with patch("apps.tutor.apps.sys.argv", ["manage.py", "migrate"]):
            config.ready()
        index_knowledge.assert_not_called()
