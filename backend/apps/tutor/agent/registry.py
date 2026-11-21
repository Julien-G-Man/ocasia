"""LangChain tool registry for the Django tutor agent."""

from langchain_core.tools import StructuredTool

from apps.tutor.agent.tools.content import (
    evaluate_answer,
    explain_concept,
    generate_flashcards,
    generate_quiz,
    request_quiz_form,
    summarize_text,
)
from apps.tutor.agent.tools.document import search_document
from apps.tutor.agent.tools.library import list_library_materials
from apps.tutor.agent.tools.performance import get_user_performance
from apps.tutor.agent.tools.search import kb_search, search_web
from apps.tutor.agent.tools.youtube import extract_youtube_transcript


TOOL_DESCRIPTIONS = {
    "kb_search": "Search Ocasia's knowledge base. Use first for platform-specific questions.",
    "search_web": "Search for current external facts; do not use for questions about Ocasia.",
    "extract_youtube_transcript": "Fetch the transcript and title of a YouTube study video.",
    "summarize_text": "Condense long content into key points before analysis or study content generation.",
    "request_quiz_form": "Open the inline quiz setup form when the student wants to take or create a quiz. Extract the topic; do not ask setup questions.",
    "generate_quiz": "Generate MCQ and short-answer questions using chat material, retrieved passages, or the requested topic. Uses the quiz service and AI engine.",
    "generate_flashcards": "Generate flashcards using chat material or retrieved passages. Uses the flashcards service and AI engine.",
    "evaluate_answer": "Evaluate a student's free-text answer against the correct answer. MCQ scoring is deterministic and should not use this tool.",
    "explain_concept": "Explain a flashcard or quiz answer to a student who is confused.",
    "search_document": "Search the indexed platform knowledge and PDF/PowerPoint study-material corpus using hybrid vector and BM25 retrieval. Return and cite the most useful source and page.",
    "get_user_performance": "Fetch the signed-in student's live quiz performance: average score, per-topic accuracy (weakest first), recent quizzes, and topics due for review. Use when the student asks about their progress, scores, weak areas, or what to study next.",
    "list_library_materials": "List community study materials in the library with direct file links. Use when the student asks what materials are available or wants a particular file. Present each result as a markdown link [Title](url) so it opens in a new tab.",
}

TOOL_TIMEOUTS = {
    "kb_search": 5.0,
    "search_web": 12.0,
    "extract_youtube_transcript": 35.0,
    "summarize_text": 35.0,
    "request_quiz_form": 2.0,
    "generate_quiz": 120.0,
    "generate_flashcards": 90.0,
    "evaluate_answer": 25.0,
    "explain_concept": 25.0,
    "search_document": 20.0,
    "get_user_performance": 10.0,
    "list_library_materials": 10.0,
}

_HANDLERS = {
    "kb_search": kb_search,
    "search_web": search_web,
    "extract_youtube_transcript": extract_youtube_transcript,
    "summarize_text": summarize_text,
    "request_quiz_form": request_quiz_form,
    "generate_quiz": generate_quiz,
    "generate_flashcards": generate_flashcards,
    "evaluate_answer": evaluate_answer,
    "explain_concept": explain_concept,
    "get_user_performance": get_user_performance,
    "list_library_materials": list_library_materials,
}


def get_tools() -> list[StructuredTool]:
    """Build the tutor's tool list, including retrieval over indexed documents."""
    handlers = {**_HANDLERS, "search_document": search_document}
    return [
        StructuredTool.from_function(
            coroutine=handler,
            name=name,
            description=TOOL_DESCRIPTIONS[name],
        )
        for name, handler in handlers.items()
    ]
