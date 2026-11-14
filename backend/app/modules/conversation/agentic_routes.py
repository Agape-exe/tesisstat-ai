"""FastAPI router for Agentic Chat in TesisStat AI."""

import base64
from typing import Annotated
from urllib.parse import unquote
from uuid import UUID

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from app.modules.conversation.agentic_service import AgenticChatService


class MessageRequest(BaseModel):
    content: str


class CreateConversationRequest(BaseModel):
    retain_dataset_from: str | None = None


class ExecuteRequest(BaseModel):
    proposal_type: str = "paired"
    variable_names: list[str] = Field(default_factory=list)


class JsonUploadRequest(BaseModel):
    filename: str
    file_base64: str
    is_instrument: bool = False
    instrument_filename: str | None = None
    instrument_base64: str | None = None


def create_agentic_router(service: AgenticChatService) -> APIRouter:
    router = APIRouter(
        prefix="/api/v2/research/projects/{project_id}/agentic",
        tags=["agentic-chat"],
    )

    @router.get("/conversations")
    def list_conversations(project_id: str):
        return service.list_conversations(project_id)

    @router.post("/conversations")
    def create_conversation(
        project_id: str, body: CreateConversationRequest | None = None
    ):
        retain = body.retain_dataset_from if body else None
        return service.get_or_create_conversation(
            project_id, retain_dataset_from=retain
        )

    @router.get("/conversations/active")
    def get_active_conversation(project_id: str):
        return service.get_or_create_conversation(project_id)

    @router.get("/conversations/{conversation_id}")
    def get_conversation(project_id: str, conversation_id: str):
        return service.get_or_create_conversation(
            project_id, conversation_id=conversation_id
        )

    @router.post("/conversations/{conversation_id}/messages")
    def send_message(project_id: str, conversation_id: str, body: MessageRequest):
        return service.send_message(project_id, conversation_id, body.content)

    @router.post("/conversations/{conversation_id}/upload-json")
    def upload_dataset_json(
        project_id: str, conversation_id: str, body: JsonUploadRequest
    ):
        file_bytes = base64.b64decode(body.file_base64)
        instrument_bytes = (
            base64.b64decode(body.instrument_base64) if body.instrument_base64 else None
        )
        return service.upload_dataset(
            project_id=project_id,
            conversation_id=conversation_id,
            file_bytes=file_bytes,
            filename=body.filename,
            is_instrument=body.is_instrument,
            instrument_bytes=instrument_bytes,
            instrument_filename=body.instrument_filename,
        )

    @router.post("/conversations/{conversation_id}/upload")
    async def upload_dataset_stream(
        project_id: str,
        conversation_id: str,
        request: Request,
        x_file_name: str = Header(default="datos.xlsx"),
        x_is_instrument: str = Header(default="false"),
    ):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
        filename = unquote(x_file_name) or "datos.xlsx"
        is_instrument = x_is_instrument.lower() in ("true", "1")
        return service.upload_dataset(
            project_id=project_id,
            conversation_id=conversation_id,
            file_bytes=bytes(data),
            filename=filename,
            is_instrument=is_instrument,
        )

    @router.post("/conversations/{conversation_id}/execute")
    def execute_analysis(
        project_id: str, conversation_id: str, body: ExecuteRequest | None = None
    ):
        proposal_type = body.proposal_type if body else "paired"
        var_names = body.variable_names if body else []
        return service.execute_analysis(
            project_id=project_id,
            conversation_id=conversation_id,
            proposal_type=proposal_type,
            variable_names=var_names,
        )

    return router
