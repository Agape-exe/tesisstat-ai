"""Independent, unauthenticated development app. Never deploy with student data."""

import logging
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.modules.research.datasets.readers import DatasetLimits, InvalidDataset
from app.modules.research.datasets.routes import create_router as create_dataset_router
from app.modules.research.datasets.sqlite_repository import (
    DatasetHasDerivatives,
    DatasetStorageError,
    SQLiteDatasetRepository,
)
from app.modules.research.datasets.use_cases import DatasetNotFound, DatasetService
from app.modules.research.documents.extraction import ExtractionLimits, ExtractionService
from app.modules.research.documents.routes import create_router as create_document_router
from app.modules.research.documents.sqlite_repository import (
    DocumentStorageError,
    SQLiteDocumentRepository,
)
from app.modules.research.documents.use_cases import (
    DocumentNotFound,
    DocumentService,
    InvalidDocument,
)
from app.modules.research.eda.analyzer import ExploratoryAnalyzer
from app.modules.research.eda.routes import create_router as create_eda_router
from app.modules.research.eda.sqlite_repository import EDAStorageError, SQLiteEDARepository
from app.modules.research.eda.use_cases import EDANotFound, EDAService
from app.modules.research.methodology.review import ReviewService
from app.modules.research.methodology.routes import create_router as create_methodology_router
from app.modules.research.methodology.service import (
    MethodologyLimits,
    MethodologyProvider,
    MethodologyService,
)
from app.modules.research.methodology.sqlite_repository import SQLiteMethodologyRepository
from app.modules.research.packages.routes import create_router as create_package_router
from app.modules.research.packages.sqlite_repository import SQLitePackageRepository
from app.modules.research.packages.use_cases import PackageService
from app.modules.research.preparation.engine import InvalidPlan
from app.modules.research.preparation.routes import create_router as create_preparation_router
from app.modules.research.preparation.sqlite_repository import SQLitePreparationRepository
from app.modules.research.preparation.use_cases import PreparationService, PreviewConflict
from app.modules.research.projects.repository import ProjectRepository
from app.modules.research.projects.routes import create_router
from app.modules.research.projects.sqlite_repository import SQLiteProjectRepository
from app.modules.research.projects.use_cases import ProjectNotFound, ProjectService
from app.shared.adapters.cloudflare import CloudflareLanguageModel, CloudflareSettings

logger = logging.getLogger(__name__)


class ResearchDevSettings(CloudflareSettings):
    research_db_path: Path = Path(".cache/research/projects.sqlite3")
    research_documents_path: Path = Path(".cache/research/documents")
    research_datasets_path: Path = Path(".cache/research/datasets")
    research_dataset_max_bytes: int = 10 * 1024 * 1024
    research_dataset_max_rows: int = 50000
    research_dataset_max_columns: int = 200
    research_dataset_preview_rows: int = 20
    research_dataset_max_zip_bytes: int = 50 * 1024 * 1024
    research_extraction_max_pages: int = 100
    research_extraction_max_units: int = 10000
    research_extraction_max_characters: int = 200000
    research_extraction_max_content_bytes: int = 20 * 1024 * 1024
    research_methodology_max_characters: int = 6000
    research_methodology_max_attempts: int = 3
    research_methodology_retry_seconds: int = 30


def create_app(
    repository: ProjectRepository | None = None,
    settings: ResearchDevSettings | None = None,
    methodology_provider: MethodologyProvider | None = None,
) -> FastAPI:
    settings = settings or ResearchDevSettings()
    if repository is None:
        repository = SQLiteProjectRepository(settings.research_db_path)
    app = FastAPI(title="TesisStat Research — development only", version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-File-Name"],
        allow_credentials=False,
    )

    @app.exception_handler(ProjectNotFound)
    async def not_found(request: Request, exc: ProjectNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "No se encontró el proyecto."})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = {}
        is_review = "/methodology/review" in request.url.path
        for error in exc.errors():
            field = (
                ".".join(str(part) for part in error["loc"] if part != "body")
                if is_review
                else str(error["loc"][-1])
            )
            kind = error["type"]
            context = error.get("ctx", {})
            if kind == "string_too_short":
                message = f"Ingresa al menos {context['min_length']} caracteres."
            elif kind == "string_too_long":
                message = f"Usa como máximo {context['max_length']} caracteres."
            elif kind == "missing":
                message = "Este campo es obligatorio."
            elif field == "academic_year":
                message = "Ingresa un año entero entre 1900 y 2100, o déjalo vacío."
            elif field == "degree":
                message = "Selecciona un grado académico válido."
            elif kind == "extra_forbidden":
                message = "Este campo no está permitido."
            else:
                message = "El valor enviado no es válido."
            errors[field] = message
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Revisa los campos de metodología."
                if is_review
                else "Revisa los datos del proyecto.",
                "errors": errors,
            },
        )

    @app.exception_handler(sqlite3.Error)
    async def storage_error(request: Request, exc: sqlite3.Error) -> JSONResponse:
        logger.error("Research development storage failed", exc_info=exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "El almacenamiento local no está disponible. Intenta nuevamente."},
        )

    @app.exception_handler(DocumentStorageError)
    async def document_storage_error(request: Request, exc: DocumentStorageError) -> JSONResponse:
        logger.error("Research document storage failed", exc_info=exc)
        return JSONResponse(
            status_code=503,
            content={
                "detail": "El almacenamiento de documentos no está disponible. Intenta nuevamente."
            },
        )

    @app.exception_handler(InvalidDocument)
    async def invalid_document(request: Request, exc: InvalidDocument) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(DocumentNotFound)
    async def document_not_found(request: Request, exc: DocumentNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "No se encontró el documento."})

    @app.exception_handler(InvalidDataset)
    async def invalid_dataset(request: Request, exc: InvalidDataset) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(DatasetNotFound)
    async def dataset_not_found(request: Request, exc: DatasetNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "No se encontró el dataset."})

    @app.exception_handler(DatasetStorageError)
    async def dataset_storage_error(request: Request, exc: DatasetStorageError) -> JSONResponse:
        logger.error("Research dataset storage failed", exc_info=exc)
        return JSONResponse(
            status_code=503,
            content={
                "detail": "El almacenamiento de datasets no está disponible. Intenta nuevamente."
            },
        )

    @app.exception_handler(DatasetHasDerivatives)
    async def dataset_has_derivatives(request: Request, exc: DatasetHasDerivatives) -> JSONResponse:
        return JSONResponse(
            status_code=409, content={"detail": "El dataset tiene derivados; elimínalos primero."}
        )

    @app.exception_handler(InvalidPlan)
    async def invalid_plan(request: Request, exc: InvalidPlan) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(PreviewConflict)
    async def preview_conflict(request: Request, exc: PreviewConflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(EDANotFound)
    async def eda_not_found(request: Request, exc: EDANotFound) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"detail": "Aún no existe un análisis EDA válido."}
        )

    @app.exception_handler(EDAStorageError)
    async def eda_storage_error(request: Request, exc: EDAStorageError) -> JSONResponse:
        logger.error("Research EDA storage failed", exc_info=exc)
        return JSONResponse(
            status_code=503, content={"detail": "El reporte EDA no está disponible."}
        )

    projects = ProjectService(repository)
    document_repository = SQLiteDocumentRepository(
        settings.research_db_path, settings.research_documents_path
    )
    documents = DocumentService(document_repository, projects)
    dataset_repository = SQLiteDatasetRepository(
        settings.research_db_path, settings.research_datasets_path
    )
    datasets = DatasetService(
        dataset_repository,
        projects,
        DatasetLimits(
            max_bytes=settings.research_dataset_max_bytes,
            max_rows=settings.research_dataset_max_rows,
            max_columns=settings.research_dataset_max_columns,
            preview_rows=settings.research_dataset_preview_rows,
            max_zip_bytes=settings.research_dataset_max_zip_bytes,
        ),
    )
    extraction = ExtractionService(
        document_repository,
        document_repository,
        projects,
        ExtractionLimits(
            max_pages=settings.research_extraction_max_pages,
            max_units=settings.research_extraction_max_units,
            max_characters=settings.research_extraction_max_characters,
            max_content_bytes=settings.research_extraction_max_content_bytes,
        ),
    )
    app.include_router(create_router(projects, documents, datasets))
    app.include_router(create_document_router(documents, extraction))
    app.include_router(create_dataset_router(datasets))
    app.include_router(
        create_preparation_router(
            PreparationService(datasets, SQLitePreparationRepository(dataset_repository))
        )
    )
    app.include_router(
        create_eda_router(
            EDAService(
                datasets, SQLiteEDARepository(settings.research_db_path), ExploratoryAnalyzer()
            )
        )
    )
    methodology_repository = SQLiteMethodologyRepository(settings.research_db_path)
    methodology = MethodologyService(
        extraction,
        methodology_repository,
        methodology_provider or CloudflareLanguageModel(settings),
        MethodologyLimits(
            max_characters=settings.research_methodology_max_characters,
            max_input_tokens=settings.cloudflare_max_input_tokens,
            timeout_seconds=settings.cloudflare_timeout_seconds,
            max_attempts=settings.research_methodology_max_attempts,
            retry_seconds=settings.research_methodology_retry_seconds,
        ),
    )
    reviews = ReviewService(methodology, methodology_repository)
    app.include_router(create_methodology_router(methodology, reviews))
    app.include_router(
        create_package_router(
            PackageService(
                projects,
                documents,
                reviews,
                datasets,
                SQLitePackageRepository(settings.research_db_path),
            )
        )
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "research-dev", "version": "0.2.0"}

    return app


app = create_app()
