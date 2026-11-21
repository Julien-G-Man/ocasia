from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tutor.agent.registry import get_tools
from apps.tutor.agent.tools.library import list_library_materials
from apps.tutor.agent.tools.performance import get_user_performance


class AgentToolRegistryTests(SimpleTestCase):
    def test_registers_performance_and_library_tools(self):
        names = {tool.name for tool in get_tools()}
        self.assertIn("get_user_performance", names)
        self.assertIn("list_library_materials", names)


class UserPerformanceToolTests(SimpleTestCase):
    async def test_requires_authenticated_user(self):
        result = await get_user_performance(None)
        self.assertFalse(result["available"])

    @patch("apps.tutor.agent.tools.performance._load_performance")
    async def test_returns_live_snapshot(self, load):
        load.return_value = (True, {
            "total_quizzes": 3,
            "avg_score": 82.5,
            "all_topics": [("Algebra", 70.0, 10)],
            "recent_quizzes": [],
            "due_topics": ["Algebra"],
        })

        result = await get_user_performance(user_id=42)

        self.assertTrue(result["available"])
        self.assertEqual(result["total_quizzes"], 3)
        self.assertEqual(result["avg_score"], 82.5)
        self.assertEqual(result["due_topics"], ["Algebra"])

    @patch("apps.tutor.agent.tools.performance._load_performance")
    async def test_reports_missing_user(self, load):
        load.return_value = (False, None)

        result = await get_user_performance(user_id=42)

        self.assertFalse(result["available"])
        self.assertIn("not found", result["message"].lower())

    @patch("apps.tutor.agent.tools.performance._load_performance")
    async def test_reports_no_quiz_history(self, load):
        load.return_value = (True, None)

        result = await get_user_performance(user_id=42)

        self.assertTrue(result["available"])
        self.assertEqual(result["total_quizzes"], 0)


class LibraryMaterialsToolTests(SimpleTestCase):
    @patch("apps.tutor.agent.tools.library._query_materials")
    async def test_formats_materials_with_links(self, query):
        query.return_value = [
            SimpleNamespace(
                id=1,
                title="Calculus Notes",
                subject="mathematics",
                original_filename="calculus.pdf",
                file_url="https://res.cloudinary.com/demo/raw/upload/calculus.pdf",
                file_size_display="1.2 MB",
                uploaded_by=SimpleNamespace(username="kofi"),
            ),
        ]

        result = await list_library_materials(query="calculus")

        self.assertEqual(result["count"], 1)
        material = result["materials"][0]
        self.assertEqual(material["title"], "Calculus Notes")
        self.assertEqual(material["subject"], "Mathematics")
        self.assertEqual(material["uploader"], "kofi")
        self.assertTrue(material["url"].startswith("https://"))

    @patch("apps.tutor.agent.tools.library._query_materials")
    async def test_reports_empty_results(self, query):
        query.return_value = []

        result = await list_library_materials()

        self.assertEqual(result["materials"], [])
        self.assertTrue(result["message"])