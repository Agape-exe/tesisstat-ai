import io
import zipfile
from datetime import UTC, datetime
from pathlib import PurePath
from uuid import UUID, uuid4

from app.modules.research.documents.models import Document
from app.modules.research.documents.repository import DocumentRepository
from app.modules.research.projects.use_cases import ProjectService

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


class InvalidDocument(Exception):
    pass


class DocumentNotFound(Exception):
    pass


def document_format(name: str, data: bytes) -> str:
    extension = PurePath(name.replace("\\", "/")).suffix.lower()
    if not data:
        raise InvalidDocument("El archivo está vacío.")
    if len(data) > MAX_DOCUMENT_BYTES:
        raise InvalidDocument("El archivo supera el límite de 10 MB.")
    if extension == ".pdf":
        if not data.startswith(b"%PDF-") or not data.rstrip().endswith(b"%%EOF"):
            raise InvalidDocument("El PDF no tiene una estructura válida.")
        return "pdf"
    if extension == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
                if sum(item.file_size for item in archive.infolist()) > 50 * 1024 * 1024:
                    raise InvalidDocument("El DOCX no tiene una estructura válida.")
                if archive.testzip() is not None or not {
                    "[Content_Types].xml",
                    "word/document.xml",
                }.issubset(names):
                    raise InvalidDocument("El DOCX no tiene una estructura válida.")
        except (zipfile.BadZipFile, RuntimeError, ValueError, OSError) as exc:
            raise InvalidDocument("El DOCX no tiene una estructura válida.") from exc
        return "docx"
    raise InvalidDocument("Adjunta un archivo PDF o DOCX.")


class DocumentService:
    def __init__(self, repository: DocumentRepository, projects: ProjectService) -> None:
        self.repository = repository
        self.projects = projects

    def add(self, project_id: UUID, name: str, data: bytes) -> Document:
        self.projects.get(project_id)
        format_ = document_format(name, data)
        document = Document(
            id=uuid4(),
            project_id=project_id,
            name=PurePath(name.replace("\\", "/")).name,
            format=format_,
            size=len(data),
            uploaded_at=datetime.now(UTC),
        )
        self.repository.add(document, data)
        return document

    def list(self, project_id: UUID) -> list[Document]:
        self.projects.get(project_id)
        return self.repository.list(project_id)

    def delete(self, project_id: UUID, document_id: UUID) -> None:
        self.projects.get(project_id)
        if not self.repository.delete(project_id, document_id):
            raise DocumentNotFound
