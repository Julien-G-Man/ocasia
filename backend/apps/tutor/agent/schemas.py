from dataclasses import dataclass, field


@dataclass
class TutorAgentResult:
    response: str
    tool_calls_made: list[str] = field(default_factory=list)
    action: str | None = None
    prefill: dict | None = None
