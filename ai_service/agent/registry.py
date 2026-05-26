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
from agent.tools.search import search_web, _kb_search_handler
from agent.tools.evaluate import evaluate_answer
from agent.tools.summarize import summarize_text
from agent.tools.youtube import extract_youtube_transcript
from agent.tools.quiz import _generate_quiz_handler, _request_quiz_form_handler
from agent.tools.flashcards import _generate_flashcards_handler, _explain_concept_handler


logger = logging.getLogger(__name__)


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

    "request_quiz_form": {
        "definition": ToolDefinition(
            name="request_quiz_form",
            description=(
                "Signal that the user wants to take a quiz. "
                "Call this immediately when the user expresses intent to take, create, or be quizzed on a topic. "
                "Pass the topic the user mentioned as 'topic'. "
                "Do NOT ask the user for more details — just call this tool. "
                "An inline setup form will appear in the chat below for the user to fill in."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The subject or topic the user wants to be quizzed on (extracted from conversation).",
                        "default": "",
                    },
                },
                "required": [],
            },
        ),
        "handler": _request_quiz_form_handler,
        "timeout": 2.0,
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
