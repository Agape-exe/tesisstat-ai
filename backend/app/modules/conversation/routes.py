from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.modules.conversation.models import ConversationDraft, MessageDraft
from app.modules.conversation.service import ConversationService


def create_router(service: ConversationService) -> APIRouter:
    router = APIRouter(
        prefix="/api/research/projects/{project_id}/conversations",
        tags=["Conversations (development)"],
    )

    @router.get("/status")
    def status(project_id: UUID):
        return service.status(project_id)

    @router.post("", status_code=201)
    def create(project_id: UUID, draft: ConversationDraft):
        return service.create(project_id, draft.title)

    @router.get("")
    def list_conversations(project_id: UUID, offset: int = Query(default=0, ge=0)):
        return service.list(project_id, offset)

    @router.get("/{conversation_id}")
    def get(
        project_id: UUID, conversation_id: UUID, before: int | None = Query(default=None, ge=1)
    ):
        return service.get(project_id, conversation_id, before)

    @router.post("/{conversation_id}/messages")
    def send(project_id: UUID, conversation_id: UUID, draft: MessageDraft):
        return service.send(project_id, conversation_id, draft)

    @router.delete("/{conversation_id}", status_code=204)
    def delete(project_id: UUID, conversation_id: UUID):
        service.delete(project_id, conversation_id)
        return Response(status_code=204)

    return router
