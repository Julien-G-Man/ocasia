"""
Agent Tool Registry

Single source of truth for all tools exposed to the AI.

Each entry contains:
  definition  -- ToolDefinition (name, description, JSON Schema)
  handler     -- async callable(**input) -> any
  timeout     -- per-tool execution timeout in seconds

To add a new tool: write a handler in agent/tools/, add a
ToolDefinition with a strict input_schema, register it here.
"""

import logging
from typing import Callable

from agent.schemas import ToolDefinition
from agent.tools.youtube import extract_youtube_transcript
from agent.tools.evaluate import evaluate_answer
from agent.tools.summarize import summarize_text
from agent.tools.search import search_web


async def _kb_search_handler(query: str, top_k: int = 4) -> dict:
    from kb.loader import kb_store
    results = kb_store.search(query, top_k=int(top_k))
    if not results:
        return {"chunks": [], "note": "No relevant platform knowledge found."}
    return {
        "chunks": [
            {"heading": r["heading"], "text": r["text"]}
            for r in results
        ]
    }

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inline handlers for quiz / flashcard generation.
# These import from services/ and call ai_client directly, avoiding an
# HTTP round-trip from FastAPI back to itself.
# ---------------------------------------------------------------------------

async def _generate_quiz_handler(
    study_text: str,
    subject: str,
    difficulty: str = "medium",
    num_mcq: int = 5,
    num_short: int = 0,
) -> dict:
    from services.quiz.routes import _normalize_study_text, _parse_json_safe
    from services.quiz.prompts import _build_quiz_prompt
    from services.quiz.schemas import QuizRequest
    from core.ai_client import ai_client
    from core.http import get_async_client

    num_mcq = max(1, min(int(num_mcq), 20))
    num_short = max(0, min(int(num_short), 5))
    difficulty = difficulty.lower() if difficulty.lower() in ("easy", "medium", "hard") else "medium"

    payload = QuizRequest(
        subject=subject,
        study_text=_normalize_study_text(study_text),
        num_mcq=num_mcq,
        num_short=num_short,
        difficulty=difficulty,
    )
    prompt = _build_quiz_prompt(payload)
    estimated_tokens = max(2048, min(8192, num_mcq * 120 + num_short * 80 + 512))

    client = await get_async_client()
    raw = await ai_client.generate_content(client=client, prompt=prompt, max_tokens=estimated_tokens, timeout=60)

    text = raw if isinstance(raw, str) else str(raw)
    data = _parse_json_safe(text)
    if not data:
        raise ValueError("AI returned an unreadable quiz format.")

    return {
        "mcq_questions": data.get("mcq_questions", []),
        "short_questions": data.get("short_questions", []),
        "subject": subject,
        "difficulty": difficulty,
    }


async def _generate_flashcards_handler(
    text: str,
    subject: str,
    num_cards: int = 10,
    difficulty: str = "intermediate",
    prompt: str = "",
) -> dict:
    from services.flashcards.routes import _normalize_cards
    from services.flashcards.prompts import DIFFICULTY_PROMPTS
    from core.ai_client import ai_client
    from core.http import get_async_client

    num_cards = max(1, min(int(num_cards), 30))
    difficulty_prompt = DIFFICULTY_PROMPTS.get(difficulty, DIFFICULTY_PROMPTS.get("intermediate", ""))

    full_prompt = (
        f"You are an expert study assistant.\n\n"
        f"Subject: {subject}\n\n"
        f"Content:\n{text[:16000]}\n\n"
        f"Additional instructions:\n{prompt}\n\n"
        f"Difficulty level:\n{difficulty_prompt}\n\n"
        f"Create {num_cards} flashcards.\n\n"
        f'Return ONLY valid JSON:\n[{{"question": "...", "answer": "..."}}]'
    )

    client = await get_async_client()
    raw = await ai_client.generate_content(client=client, prompt=full_prompt, max_tokens=1200, timeout=30)
    cards = _normalize_cards(raw)
    if not cards:
        raise ValueError("AI returned an unreadable flashcard format.")
    return {"cards": cards}


async def _explain_concept_handler(question: str, answer: str) -> dict:
    from core.ai_client import ai_client
    from core.http import get_async_client

    full_prompt = (
        f"A student is struggling with this flashcard.\n\n"
        f"Question: {question}\n"
        f"Correct Answer: {answer}\n\n"
        f"Explain this concept clearly in 3 short sentences like a tutor helping a beginner."
    )
    client = await get_async_client()
    raw = await ai_client.generate_content(client=client, prompt=full_prompt, max_tokens=250, timeout=20)
    explanation = raw.strip() if isinstance(raw, str) else str(raw).strip()
    return {"explanation": explanation}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, dict] = {

    "kb_search": {
        "definition": ToolDefinition(
            name="kb_search",
            description=(
                "Search the Lamla platform knowledge base for information about the platform, "
                "its features, how things work, pricing, or support contacts. "
                "Always call this first for any platform-specific question before using web_search. "
                "Returns the most relevant knowledge chunks."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to look up in the knowledge base.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of chunks to return (default 4).",
                        "default": 4,
                    },
                },
                "required": ["query"],
            },
        ),
        "handler": _kb_search_handler,
        "timeout": 5.0,
    },

    "extract_youtube_transcript": {
        "definition": ToolDefinition(
            name="extract_youtube_transcript",
            description=(
                "Fetch the full transcript and title from a YouTube video URL. "
                "Use this before generating a quiz or flashcards from a YouTube video. "
                "Returns the transcript text, video title, and video ID."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Any YouTube URL (watch?v=, youtu.be/, /shorts/, /embed/)",
                    },
                },
                "required": ["url"],
            },
        ),
        "handler": extract_youtube_transcript,
        "timeout": 30.0,
    },

    "summarize_text": {
        "definition": ToolDefinition(
            name="summarize_text",
            description=(
                "Condense a body of text into key points. "
                "Use when content is too long for direct processing, "
                "or when the user explicitly asks for a summary."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to summarize."},
                    "max_words": {
                        "type": "integer",
                        "description": "Target summary length in words (default 300).",
                        "default": 300,
                    },
                    "focus": {
                        "type": "string",
                        "description": "Optional framing instruction (e.g. 'focus on definitions').",
                        "default": "",
                    },
                },
                "required": ["text"],
            },
        ),
        "handler": summarize_text,
        "timeout": 30.0,
    },

    "evaluate_answer": {
        "definition": ToolDefinition(
            name="evaluate_answer",
            description=(
                "Evaluate a student's short-answer response against the correct answer. "
                "Returns score (0.0-1.0), is_correct bool, and brief reasoning. "
                "Only for free-text answers   MCQ is scored deterministically by Django."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The quiz question."},
                    "correct_answer": {"type": "string", "description": "The model answer."},
                    "user_answer": {"type": "string", "description": "The student's answer."},
                },
                "required": ["question", "correct_answer", "user_answer"],
            },
        ),
        "handler": evaluate_answer,
        "timeout": 25.0,
    },

    "generate_quiz": {
        "definition": ToolDefinition(
            name="generate_quiz",
            description=(
                "Generate a quiz from a body of study text. "
                "Returns Agent and/or short-answer questions. "
                "Use when the user provides text or a transcript and wants a quiz."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "study_text": {"type": "string", "description": "Study material to generate from."},
                    "subject": {"type": "string", "description": "Topic label (e.g. 'Biology')."},
                    "difficulty": {
                        "type": "string",
                        "enum": ["easy", "medium", "hard"],
                        "default": "medium",
                    },
                    "num_mcq": {"type": "integer", "default": 5, "description": "MCQ count (1-20)."},
                    "num_short": {"type": "integer", "default": 0, "description": "Short-answer count (0-5)."},
                },
                "required": ["study_text", "subject"],
            },
        ),
        "handler": _generate_quiz_handler,
        "timeout": 90.0,
    },

    "generate_flashcards": {
        "definition": ToolDefinition(
            name="generate_flashcards",
            description=(
                "Generate study flashcards from a body of text. "
                "Each card has a question and answer. "
                "Use when the user provides content and wants flashcards."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Study material."},
                    "subject": {"type": "string", "description": "Topic label."},
                    "num_cards": {"type": "integer", "default": 10, "description": "Card count (1-30)."},
                    "difficulty": {
                        "type": "string",
                        "default": "intermediate",
                        "description": "beginner | intermediate | advanced",
                    },
                    "prompt": {
                        "type": "string",
                        "default": "",
                        "description": "Optional extra instruction.",
                    },
                },
                "required": ["text", "subject"],
            },
        ),
        "handler": _generate_flashcards_handler,
        "timeout": 45.0,
    },

    "explain_concept": {
        "definition": ToolDefinition(
            name="explain_concept",
            description=(
                "Generate a beginner-friendly explanation for a concept given "
                "a question and its correct answer. "
                "Use when a student is confused about a specific flashcard or quiz answer."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The flashcard or quiz question."},
                    "answer": {"type": "string", "description": "The correct answer."},
                },
                "required": ["question", "answer"],
            },
        ),
        "handler": _explain_concept_handler,
        "timeout": 20.0,
    },

    "search_web": {
        "definition": ToolDefinition(
            name="search_web",
            description=(
                "Search the web for current information on a topic. "
                "Use ONLY when the student's question requires up-to-date facts, "
                "recent events, or information not available in the platform knowledge base. "
                "Do NOT use for questions about the Lamla platform or general concepts "
                "you can answer from training knowledge."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Specific search query — be precise, not verbose.",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results to retrieve (1-5, default 3).",
                        "default": 3,
                    },
                },
                "required": ["query"],
            },
        ),
        "handler": search_web,
        "timeout": 12.0,
    },
}


def get_all_definitions() -> list[ToolDefinition]:
    return [entry["definition"] for entry in TOOL_REGISTRY.values()]


def get_definitions(names: list[str] | None) -> list[ToolDefinition]:
    """Return definitions for the requested tool names. None = all tools."""
    if names is None:
        return get_all_definitions()
    result = []
    for name in names:
        if name in TOOL_REGISTRY:
            result.append(TOOL_REGISTRY[name]["definition"])
        else:
            logger.warning("[agent:registry] unknown tool requested: %s", name)
    return result


def get_handler(name: str) -> Callable:
    if name not in TOOL_REGISTRY:
        raise KeyError(f"No tool registered with name '{name}'")
    return TOOL_REGISTRY[name]["handler"]


def get_timeout(name: str) -> float:
    return TOOL_REGISTRY.get(name, {}).get("timeout", 30.0)
