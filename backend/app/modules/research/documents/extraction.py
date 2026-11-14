"""Bounded, local text extraction independent of the HTTP adapter."""

import io
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import UUID

from docx import Document as WordDocument
from docx.table import Table
from docx.text.paragraph import Paragraph
from pydantic import BaseModel, Field
from pypdf import PdfReader, apply_configuration

from app.modules.research.documents.repository import DocumentRepository
from app.modules.research.documents.use_cases import DocumentNotFound
from app.modules.research.projects.use_cases import ProjectService


class ExtractionLimits(BaseModel):
    max_pages: int = Field(default=100, gt=0)
    max_units: int = Field(default=10000, gt=0)
    max_characters: int = Field(default=200000, gt=0)
    max_content_bytes: int = Field(default=20 * 1024 * 1024, gt=0)


class ExtractionResult(BaseModel):
    document_id: UUID
    project_id: UUID
    status: Literal["completed", "no_text", "failed"]
    text: str
    character_count: int
    units_processed: int
    processed_at: datetime
    warnings: list[str]
    truncated: bool


class TextExtractor(Protocol):
    def extract(self, data: bytes, limits: ExtractionLimits) -> tuple[str, int, bool]: ...


class ExtractionRepository(Protocol):
    def get_extraction(self, project_id: UUID, document_id: UUID) -> ExtractionResult | None: ...
    def save_extraction(self, result: ExtractionResult) -> None: ...


class ExtractionFailed(Exception):
    pass


def _append(parts: list[str], value: str, count: int, maximum: int) -> tuple[int, bool]:
    value = value.strip()
    if not value:
        return count, False
    available = maximum - count
    if parts:
        available -= 2
    if available <= 0:
        return count, True
    clipped = value[:available]
    parts.append(clipped)
    return count + len(clipped) + (2 if len(parts) > 1 else 0), len(clipped) < len(value)


class PDFTextExtractor:
    def extract(self, data: bytes, limits: ExtractionLimits) -> tuple[str, int, bool]:
        try:
            with apply_configuration(
                zlib_maximum_output_length=limits.max_content_bytes,
                lzw_maximum_output_length=limits.max_content_bytes,
                run_length_maximum_output_length=limits.max_content_bytes,
                brotli_maximum_output_length=limits.max_content_bytes,
                array_based_stream_maximum_output_length=limits.max_content_bytes,
            ):
                reader = PdfReader(io.BytesIO(data), strict=True)
                if reader.is_encrypted:
                    raise ExtractionFailed("El PDF está protegido y no se puede leer.")
                total = len(reader.pages)
                parts: list[str] = []
                count = 0
                processed = 0
                truncated = total > limits.max_pages
                for page in reader.pages[: limits.max_pages]:
                    contents = page.get_contents()
                    if contents is not None and len(contents.get_data()) > limits.max_content_bytes:
                        raise ExtractionFailed("El PDF excede el límite de procesamiento.")
                    value = page.extract_text() or ""
                    processed += 1
                    count, clipped = _append(parts, value, count, limits.max_characters)
                    truncated |= clipped
                    if clipped:
                        break
                return "\n\n".join(parts), processed, truncated
        except ExtractionFailed:
            raise
        except Exception as exc:
            raise ExtractionFailed("El PDF no se pudo leer.") from exc


class DOCXTextExtractor:
    def extract(self, data: bytes, limits: ExtractionLimits) -> tuple[str, int, bool]:
        try:
            document = WordDocument(io.BytesIO(data))
            parts: list[str] = []
            count = 0
            processed = 0
            for block in document.iter_inner_content():
                if isinstance(block, Paragraph):
                    values = [block.text]
                elif isinstance(block, Table):
                    values = ["\t".join(cell.text for cell in row.cells) for row in block.rows]
                else:
                    continue
                for value in values:
                    if processed >= limits.max_units:
                        return "\n\n".join(parts), processed, True
                    processed += 1
                    count, clipped = _append(parts, value, count, limits.max_characters)
                    if clipped:
                        return "\n\n".join(parts), processed, True
            return "\n\n".join(parts), processed, False
        except Exception as exc:
            raise ExtractionFailed("El DOCX no se pudo leer.") from exc


class ExtractionService:
    def __init__(
        self,
        documents: DocumentRepository,
        results: ExtractionRepository,
        projects: ProjectService,
        limits: ExtractionLimits,
        extractors: dict[str, TextExtractor] | None = None,
    ) -> None:
        self.documents = documents
        self.results = results
        self.projects = projects
        self.limits = limits
        self.extractors = extractors or {"pdf": PDFTextExtractor(), "docx": DOCXTextExtractor()}

    def _document(self, project_id: UUID, document_id: UUID):
        self.projects.get(project_id)
        document = self.documents.get(project_id, document_id)
        if document is None:
            raise DocumentNotFound
        return document

    def get(self, project_id: UUID, document_id: UUID) -> ExtractionResult | None:
        self._document(project_id, document_id)
        return self.results.get_extraction(project_id, document_id)

    def extract(self, project_id: UUID, document_id: UUID) -> ExtractionResult:
        document = self._document(project_id, document_id)
        cached = self.results.get_extraction(project_id, document_id)
        if cached is not None and cached.status != "failed":
            return cached
        try:
            data = self.documents.read(project_id, document_id)
            text, units, truncated = self.extractors[document.format].extract(data, self.limits)
            status = "completed" if text else "no_text"
            warnings = []
            if not text:
                warnings.append(
                    "No hay texto seleccionable en las páginas procesadas; puede requerir OCR."
                    if document.format == "pdf"
                    else "El DOCX no contiene texto legible."
                )
            if truncated:
                warnings.append("La extracción alcanzó un límite de procesamiento.")
        except ExtractionFailed as exc:
            text, units, truncated, status = "", 0, False, "failed"
            warnings = [str(exc)]
        result = ExtractionResult(
            document_id=document_id,
            project_id=project_id,
            status=status,
            text=text,
            character_count=len(text),
            units_processed=units,
            processed_at=datetime.now(UTC),
            warnings=warnings,
            truncated=truncated,
        )
        self.results.save_extraction(result)
        return result
