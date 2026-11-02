from typing import Protocol
from uuid import UUID

from app.modules.research.documents.models import Document


class DocumentRepository(Protocol):
    def add(self, document: Document, data: bytes) -> None: ...
    def list(self, project_id: UUID) -> list[Document]: ...
    def delete(self, project_id: UUID, document_id: UUID) -> bool: ...
