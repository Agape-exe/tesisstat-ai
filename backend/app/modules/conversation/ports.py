from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.conversation.models import Conversation, Message


class ResponseGenerator(Protocol):
    @property
    def configured(self) -> bool: ...

    def chat(self, messages: list[dict[str, str]], *, max_tokens: int) -> str: ...


class ConversationRepository(Protocol):
    def create(self, project_id: UUID, title: str) -> Conversation: ...
    def list(self, project_id: UUID, limit: int, offset: int) -> list[Conversation]: ...
    def get(self, project_id: UUID, conversation_id: UUID) -> Conversation: ...
    def messages(
        self,
        conversation_id: UUID,
        limit: int,
        before: int | None = None,
        *,
        completed_only: bool = False,
    ) -> list[Message]: ...
    def claim(
        self,
        conversation_id: UUID,
        request_id: UUID,
        content: str,
        timeout: float,
        *,
        fingerprint: str | None = None,
        context: dict | None = None,
    ) -> list[Message] | None: ...
    def complete(
        self,
        conversation_id: UUID,
        request_id: UUID,
        content: str,
        context: dict | None = None,
        *,
        guard=None,
    ) -> list[Message]: ...
    def fail(
        self, conversation_id: UUID, request_id: UUID, context: dict | None = None
    ) -> None: ...
    def delete(self, project_id: UUID, conversation_id: UUID) -> None: ...
