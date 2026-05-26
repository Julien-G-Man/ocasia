from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ToolDefinition(BaseModel):
    """
    Describes a single capability exposed to the AI.
    Keep descriptions precise -- vague descriptions cause bad tool selection.
    """
    name: str
    description: str
    input_schema: dict  # JSON Schema for inputs


class ToolCall(BaseModel):
    """A single tool invocation requested by the AI."""
    tool_use_id: str        # Anthropic-assigned ID; echoed back in ToolResult
    name: str
    input: dict = Field(default_factory=dict)


class ToolResult(BaseModel):
    """The outcome of executing one ToolCall."""
    tool_use_id: str
    name: str
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0


class OrchestratorRequest(BaseModel):
    """
    Sent by Django to POST /agent/orchestrate.

    messages: Anthropic messages format [{role, content}, ...]
    tools:    Optional whitelist of tool names. None = all registered tools.
    system_prompt: Platform context, KB chunks, persona -- prepended before the loop.
    """
    messages: list[dict]
    tools: list[str] | None = None
    max_iterations: int = Field(default=5, ge=1, le=10)
    max_tokens: int = Field(default=1024, ge=64, le=8192)
    system_prompt: str = ""


class OrchestratorResponse(BaseModel):
    """Returned by the orchestrator after the AI finishes reasoning."""
    response: str
    tool_calls_made: list[str] = Field(default_factory=list)
    iterations: int = 0
    error: str | None = None


class ChatRequest(BaseModel):
    """
    Sent by Django to POST /agent/chat.
    Django handles auth, DB, and user stats — FastAPI handles all AI work.
    """
    message: str
    conversation_history: list[dict] = Field(default_factory=list)
    tutor_mode: str = "direct"   # "direct" | "socratic"
    user_stats: dict | None = None
    file_text: str | None = None
    user_id: int | None = None


class AgentQuizGenerateRequest(BaseModel):
    """
    Sent by Django to POST /agent/quiz/generate/.
    Bypasses the conversational loop — dedicated quiz generation endpoint.
    """
    topic: str
    num_questions: int = Field(default=10, ge=5, le=20)
    time_limit: int = Field(default=15, ge=5, le=60)
    user_stats: dict | None = None
