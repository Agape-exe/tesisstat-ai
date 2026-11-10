"""Independent, unauthenticated development app. Never deploy with student data."""

import logging
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import Field

from app.modules.conversation.models import ConversationError
from app.modules.conversation.ports import ResponseGenerator
from app.modules.conversation.research_context import ResearchContextBuilder
from app.modules.conversation.routes import create_router as create_conversation_router
from app.modules.conversation.service import ConversationService, ConversationSettings
from app.modules.conversation.sqlite_repository import SQLiteConversationRepository
from app.modules.research.context.repository import ContextError
from app.modules.research.context.routes import create_router as create_context_router
from app.modules.research.context.sqlite_repository import SQLiteContextRepository
from app.modules.research.context.use_cases import ContextService
from app.modules.research.data_workspace.repository import WorkspaceRepository
from app.modules.research.data_workspace.routes import create_router as create_workspace_router
from app.modules.research.data_workspace.service import WorkspaceService
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
from app.modules.research.instrument.extraction_provider import (
    InstrumentExtractionProvider,
    InstrumentLanguageModel,
)
from app.modules.research.instrument.extraction_service import (
    CandidateIntegrityError,
    DocumentExtractionConsentRequired,
    IncompleteCandidateError,
    InstrumentExtractionService,
)
from app.modules.research.instrument.reader import ResearchInstrumentContextReader
from app.modules.research.instrument.repository import (
    InstrumentConflict,
    InstrumentNotConfirmedError,
    InstrumentNotFound,
    InstrumentStaleError,
    InstrumentValidationError,
)
from app.modules.research.instrument.routes import create_router as create_instrument_router
from app.modules.research.instrument.service import InstrumentService
from app.modules.research.instrument.sqlite_repository import SQLiteInstrumentRepository
from app.modules.research.intents.repository import SQLiteEvidenceStore
from app.modules.research.intents.service import IntentService
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
from app.modules.research.sources.repository import SourceRepository
from app.modules.research.sources.routes import create_router as create_source_router
from app.modules.research.sources.service import SourceService
from app.orchestration.analysis_repository import SQLiteAnalysisRepository
from app.orchestration.analysis_routes import create_router as create_analysis_router
from app.orchestration.analysis_routes import local_only
from app.orchestration.analysis_service import ResearchAnalysisService
from app.orchestration.diagnostic_routes import create_router as create_diagnostic_router
from app.orchestration.diagnostic_service import DiagnosticService
from app.orchestration.research_statistics import ResearchInputError, ResearchStatisticsBridge
from app.orchestration.statistics_routes import create_statistics_router
from app.shared.adapters.cloudflare import CloudflareLanguageModel

logger = logging.getLogger(__name__)


class ResearchDevSettings(ConversationSettings):
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
        ]
    )
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
    research_integrity_secret: str | None = None


def create_app(
    repository: ProjectRepository | None = None,
    settings: ResearchDevSettings | None = None,
    methodology_provider: MethodologyProvider | None = None,
    conversation_provider: ResponseGenerator | None = None,
    instrument_provider: InstrumentExtractionProvider | InstrumentLanguageModel | None = None,
    instrument_extraction_service: InstrumentExtractionService | None = None,
) -> FastAPI:
    settings = settings or ResearchDevSettings()
    if settings.app_env != "development":
        raise RuntimeError("La API de demostración solo admite APP_ENV=development.")
    if repository is None:
        repository = SQLiteProjectRepository(settings.research_db_path)
    app = FastAPI(title="TesisStat Research — development only", version="0.3.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-File-Name"],
        allow_credentials=False,
    )

    @app.middleware("http")
    async def require_loopback(request: Request, call_next):
        from fastapi import HTTPException

        try:
            local_only(request)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        if "/context/suggestions" in request.url.path and request.method == "POST":
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 800000:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "limit_exceeded",
                                "message": "La respuesta es demasiado grande. "
                                "Pide un resumen estructurado; no pegues la tesis completa.",
                                "fields": [],
                                "current_revision": None,
                            }
                        },
                    )
            request._body = bytes(body)
        if "/conversations" in request.url.path:
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > settings.conversation_max_request_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "La solicitud del chat es demasiado grande."},
                    )
            request._body = bytes(body)
        return await call_next(request)

    @app.exception_handler(ContextError)
    async def context_error(request: Request, exc: ContextError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "fields": exc.fields,
                    "current_revision": exc.current_revision,
                }
            },
        )

    @app.exception_handler(ConversationError)
    async def conversation_error(request: Request, exc: ConversationError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status, content={"detail": exc.detail, "code": exc.code}
        )

    @app.exception_handler(ProjectNotFound)
    async def not_found(request: Request, exc: ProjectNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "No se encontró el proyecto."})

    @app.exception_handler(ResearchInputError)
    async def research_input_error(request: Request, exc: ResearchInputError) -> JSONResponse:
        return JSONResponse(
            status_code=404 if exc.code == "project_missing" else 409,
            content={"detail": str(exc), "code": exc.code},
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        if request.url.path.startswith("/api/v2/"):
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "invalid_payload",
                        "message": "Revisa los campos enviados.",
                        "fields": [
                            "/" + "/".join(str(p) for p in e["loc"] if p != "body")
                            for e in exc.errors()
                        ],
                        "current_revision": None,
                    }
                },
            )
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
                else "Revisa los datos del mensaje."
                if "/conversations" in request.url.path
                else "Revisa los datos del proyecto.",
                "errors": errors,
            },
        )

    @app.exception_handler(sqlite3.Error)
    async def storage_error(request: Request, exc: sqlite3.Error) -> JSONResponse:
        logger.error("Research development storage failed", exc_info=exc)
        if request.url.path.startswith("/api/v2/"):
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "storage_unavailable",
                        "message": "El almacenamiento local no está disponible.",
                        "fields": [],
                        "current_revision": None,
                    }
                },
            )
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

    @app.exception_handler(InstrumentNotFound)
    async def instrument_not_found(request: Request, exc: InstrumentNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InstrumentConflict)
    async def instrument_conflict(request: Request, exc: InstrumentConflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(InstrumentValidationError)
    async def instrument_validation_error(
        request: Request, exc: InstrumentValidationError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(InstrumentStaleError)
    async def instrument_stale_error(request: Request, exc: InstrumentStaleError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": str(exc), "reasons": exc.reasons},
        )

    @app.exception_handler(InstrumentNotConfirmedError)
    async def instrument_not_confirmed(
        request: Request, exc: InstrumentNotConfirmedError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(DocumentExtractionConsentRequired)
    async def document_extraction_consent_required(
        request: Request, exc: DocumentExtractionConsentRequired
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(IncompleteCandidateError)
    async def incomplete_candidate_error(
        request: Request, exc: IncompleteCandidateError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(CandidateIntegrityError)
    async def candidate_integrity_error(
        request: Request, exc: CandidateIntegrityError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    projects = ProjectService(repository)
    sources = SourceService(
        projects,
        SourceRepository(
            settings.research_db_path,
            settings.research_datasets_path.with_name(
                settings.research_datasets_path.name + "-sources-v2"
            ),
        ),
        DatasetLimits(
            max_bytes=settings.research_dataset_max_bytes,
            max_rows=settings.research_dataset_max_rows,
            max_columns=settings.research_dataset_max_columns,
            preview_rows=settings.research_dataset_preview_rows,
            max_zip_bytes=settings.research_dataset_max_zip_bytes,
        ),
    )
    app.state.source_service = sources
    app.include_router(create_source_router(sources))
    workspace = WorkspaceService(sources, WorkspaceRepository(settings.research_db_path))
    app.state.data_workspace_service = workspace
    app.include_router(create_workspace_router(workspace))
    evidence_store = SQLiteEvidenceStore(settings.research_db_path)
    intents = IntentService(workspace, evidence_store)
    diagnostics = DiagnosticService(intents, workspace, evidence_store)
    app.state.intent_service = intents
    app.state.diagnostic_service = diagnostics
    app.include_router(create_diagnostic_router(intents, diagnostics))
    app.include_router(
        create_context_router(
            ContextService(
                projects,
                SQLiteContextRepository(settings.research_db_path),
                actor_ref="local",
            )
        )
    )
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
    packages = PackageService(
        projects,
        documents,
        reviews,
        datasets,
        SQLitePackageRepository(settings.research_db_path),
    )
    app.include_router(create_package_router(packages))
    instrument_repository = SQLiteInstrumentRepository(settings.research_db_path)
    instruments = InstrumentService(
        instrument_repository,
        projects,
        documents,
        methodology_repository,
        datasets,
    )
    instrument_reader = ResearchInstrumentContextReader(instruments)
    app.state.instrument_service = instruments
    app.state.instrument_reader = instrument_reader
    if instrument_extraction_service is not None:
        extraction_service_inst = instrument_extraction_service
    else:
        inst_provider = instrument_provider or CloudflareLanguageModel(settings)
        integrity_secret_bytes = (
            settings.research_integrity_secret.encode("utf-8")
            if settings.research_integrity_secret
            else None
        )
        extraction_service_inst = InstrumentExtractionService(
            projects=projects,
            documents=documents,
            extraction_service=extraction,
            provider=inst_provider,
            instrument_service=instruments,
            methodology=methodology_repository,
            integrity_secret=integrity_secret_bytes,
        )
    app.state.instrument_extraction_service = extraction_service_inst
    app.include_router(create_instrument_router(instruments, extraction_service_inst))
    app.state.research_statistics_bridge = ResearchStatisticsBridge(
        projects, packages, datasets, instruments=instruments, instrument_reader=instrument_reader
    )
    app.state.research_analysis = ResearchAnalysisService(
        app.state.research_statistics_bridge,
        SQLiteAnalysisRepository(settings.research_db_path),
        document_repository,
    )
    app.include_router(create_analysis_router(app.state.research_analysis))
    app.include_router(create_statistics_router(app.state.research_analysis))
    context = ResearchContextBuilder(
        projects,
        documents,
        methodology_repository,
        datasets,
        EDAService(datasets, SQLiteEDARepository(settings.research_db_path), ExploratoryAnalyzer()),
        packages,
        app.state.research_analysis,
        SQLitePreparationRepository(dataset_repository),
    )
    app.state.conversation_context = context
    app.include_router(
        create_conversation_router(
            ConversationService(
                projects,
                SQLiteConversationRepository(settings.research_db_path),
                conversation_provider
                if conversation_provider is not None
                else CloudflareLanguageModel(settings),
                settings,
                context,
            )
        )
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "research-dev", "version": "0.3.0"}

    return app


app = create_app()
