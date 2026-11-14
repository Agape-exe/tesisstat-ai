from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Conversation(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class Message(BaseModel):
    id: UUID
    conversation_id: UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    sequence: int
    context: dict | None = None


class ConversationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(default="Nueva conversación", min_length=1, max_length=100)


class MessageDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    content: str = Field(min_length=1, max_length=16000)
    request_id: UUID
    external_ai_consent: Literal[True]
    consent_scope: Literal["research_context_v2"]


class ConversationError(Exception):
    def __init__(self, code: str, detail: str, status: int = 409):
        self.code, self.detail, self.status = code, detail, status
        super().__init__(detail)
