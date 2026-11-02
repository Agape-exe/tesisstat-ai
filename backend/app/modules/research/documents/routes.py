from urllib.parse import unquote
from uuid import UUID

from fastapi import APIRouter, Header, Request, Response, status

from app.modules.research.documents.models import Document
from app.modules.research.documents.use_cases import (
    MAX_DOCUMENT_BYTES,
    DocumentService,
    InvalidDocument,
)


def create_router(service: DocumentService) -> APIRouter:
    router = APIRouter(
        prefix="/api/research/projects/{project_id}/documents",
        tags=["Research documents (development)"],
    )

    @router.post("", response_model=Document, status_code=status.HTTP_201_CREATED)
    async def add_document(
        project_id: UUID, request: Request, x_file_name: str = Header(default="")
    ) -> Document:
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_DOCUMENT_BYTES:
                raise InvalidDocument("El archivo supera el límite de 10 MB.")
        return service.add(project_id, unquote(x_file_name), bytes(data))

    @router.get("", response_model=list[Document])
    def list_documents(project_id: UUID) -> list[Document]:
        return service.list(project_id)

    @router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_document(project_id: UUID, document_id: UUID) -> Response:
        service.delete(project_id, document_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
