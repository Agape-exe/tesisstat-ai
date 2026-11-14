from urllib.parse import unquote
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from app.modules.research.documents.extraction import ExtractionResult, ExtractionService
from app.modules.research.documents.models import Document
from app.modules.research.documents.use_cases import (
    MAX_DOCUMENT_BYTES,
    DocumentService,
    InvalidDocument,
)


def create_router(service: DocumentService, extraction: ExtractionService) -> APIRouter:
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

    @router.post("/{document_id}/extract", response_model=ExtractionResult)
    def extract_document(project_id: UUID, document_id: UUID) -> ExtractionResult:
        return extraction.extract(project_id, document_id)

    @router.get("/{document_id}/extraction", response_model=ExtractionResult)
    def get_extraction(project_id: UUID, document_id: UUID) -> ExtractionResult:
        result = extraction.get(project_id, document_id)
        if result is None:
            raise HTTPException(
                status_code=404, detail="Aún no hay extracción para este documento."
            )
        return result

    return router
