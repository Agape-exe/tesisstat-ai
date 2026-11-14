from dataclasses import dataclass
from typing import Literal, TypedDict
from uuid import UUID

from app.modules.conversation.models import Message
from app.modules.conversation.research_context import ResearchContext

RequestType = Literal[
    "general", "methodology", "data", "results", "planning", "clarification", "blocked_execution"
]


@dataclass
class ExecutionBudget:
    deadline: float
    max_steps: int
    max_calls: int
    max_planning: int
    steps: int = 0
    calls: int = 0
    planning: int = 0


class AgentState(TypedDict):
    project_id: UUID
    conversation_id: UUID
    title: str
    project_version: str
    content: str
    history: list[Message]
    request_type: RequestType
    research: ResearchContext | None
    planning: dict
    warnings: list[str]
    answer: str
    context_bytes: int
    output_tokens: int
    budget: ExecutionBudget
    trace: dict
