"""Production application composition for TesisStat AI.

Mounts all required routers for Research, Statistics, and Agentic Conversation,
enforces CORS for production frontends (such as Vercel), applies tenant isolation,
and manages durable persistence safely.
"""

import logging
import os
import sqlite3
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.modules.conversation.agentic_routes import create_agentic_router
from app.modules.conversation.agentic_service import AgenticChatService
from app.modules.conversation.models import ConversationError
from app.modules.conversation.research_context import ResearchContextBuilder
from app.modules.conversation.routes import create_router as create_conversation_router
from app.modules.conversation.service import ConversationService, ConversationSettings
from app.modules.conversation.sqlite_repository import SQLiteConversationRepository
from app.modules.conversation.tutor_routes import create_router as create_tutor_router
from app.modules.conversation.tutor_service import TutorService
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
from app.modules.research.instrument.v2_routes import create_router as create_instrument_v2_router
from app.modules.research.instrument.v2_service import InstrumentServiceV2
from app.modules.research.intents.repository import SQLiteEvidenceStore
from app.modules.research.intents.service import IntentService
from app.modules.research.methodology.review import ReviewService
from app.modules.research.methodology.routes import create_router as create_methodology_router
from app.modules.research.methodology.service import (
    MethodologyLimits,
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
from app.modules.research.projects.models import Project, ProjectDraft
from app.modules.research.projects.routes import create_router
from app.modules.research.projects.sqlite_repository import SQLiteProjectRepository
from app.modules.research.projects.use_cases import ProjectNotFound, ProjectService
from app.modules.research.sources.repository import SourceRepository
from app.modules.research.sources.routes import create_router as create_source_router
from app.modules.research.sources.service import SourceService
from app.orchestration.analysis_repository import SQLiteAnalysisRepository
from app.orchestration.analysis_service import ResearchAnalysisService
from app.orchestration.analysis_v2_routes import create_router as create_analysis_v2_router
from app.orchestration.analysis_v2_service import AnalysisServiceV2
from app.orchestration.diagnostic_routes import create_router as create_diagnostic_router
from app.orchestration.diagnostic_service import DiagnosticService
from app.orchestration.reports_v2_service import ReportsServiceV2
from app.orchestration.research_statistics import ResearchStatisticsBridge
from app.orchestration.scores_v2 import ScoreServiceV2
from app.orchestration.statistics_routes import create_statistics_router
from app.shared.adapters.cloudflare import CloudflareLanguageModel
from app.shared.adapters.gemini import GeminiLanguageModel

logger = logging.getLogger("tesisstat.production")
current_session_token: ContextVar[str] = ContextVar("current_session_token", default="default_session")


class ProductionProjectService(ProjectService):
    """Project service with tenant isolation support."""

    def __init__(self, repository: SQLiteProjectRepository) -> None:
        super().__init__(repository)
        self.sqlite_repo = repository

    def list(self) -> list[Project]:
        sid = current_session_token.get()
        return self.sqlite_repo.list(owner_id=sid)

    def create(self, draft: ProjectDraft) -> Project:
        sid = current_session_token.get()
        now = datetime.now(UTC)
        project = Project(**draft.model_dump(), id=uuid4(), created_at=now, updated_at=now)
        self.sqlite_repo.add(project, owner_id=sid)
        return project


def create_production_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    # Determine storage directory
    storage_dir = settings.research_storage_dir
    storage_dir.mkdir(parents=True, exist_ok=True)
    db_path = storage_dir / "projects.sqlite3"
    documents_path = storage_dir / "documents"
    datasets_path = storage_dir / "datasets"
    documents_path.mkdir(parents=True, exist_ok=True)
    datasets_path.mkdir(parents=True, exist_ok=True)

    app = FastAPI(
        title="TesisStat AI",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
    )

    # 1. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Session-ID",
            "X-File-Name",
            "X-Is-Instrument",
        ],
        allow_credentials=False,
    )

    # 2. Multi-Tenant Authorization & Request Size Gate
    project_repo = SQLiteProjectRepository(db_path)
    projects = ProductionProjectService(project_repo)

    @app.middleware("http")
    async def tenant_and_size_guard(request: Request, call_next):
        # Path exemptions for health & docs
        if request.url.path in ("/health", "/api/health", "/docs", "/openapi.json"):
            return await call_next(request)

        # Extract Session / Tenant token
        auth_header = request.headers.get("Authorization", "")
        session_id = request.headers.get("X-Session-ID", "").strip()
        if not session_id and auth_header.startswith("Bearer "):
            session_id = auth_header[7:].strip()
        if not session_id:
            session_id = "default_session"

        request.state.session_id = session_id
        token = current_session_token.set(session_id)

        try:
            # Body size enforcement
            if "/conversations" in request.url.path:
                is_upload = "/upload" in request.url.path
                max_bytes = 15 * 1024 * 1024 if is_upload else 65536
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        return JSONResponse(
                            status_code=413,
                            content={
                                "detail": "El archivo es demasiado grande (máximo 10 MB)."
                                if is_upload
                                else "La solicitud del chat es demasiado grande."
                            },
                        )
                request._body = bytes(body)

            # Tenant isolation check on project URLs
            # URL structure: /api/.../projects/{project_id}/...
            path_segments = request.url.path.strip("/").split("/")
            if "projects" in path_segments:
                idx = path_segments.index("projects")
                if idx + 1 < len(path_segments):
                    project_id_str = path_segments[idx + 1]
                    # If segment is a valid UUID, verify ownership
                    try:
                        p_uuid = UUID(project_id_str)
                        owner = project_repo.get_owner(p_uuid)
                        if owner and owner not in ("local", session_id, "default_session"):
                            return JSONResponse(
                                status_code=403,
                                content={
                                    "detail": "No tienes autorización para acceder a este proyecto de investigación."
                                },
                            )
                    except ValueError:
                        pass

            response = await call_next(request)
            # Ensure session id is passed back if new
            response.headers["X-Session-ID"] = session_id
            return response
        finally:
            current_session_token.reset(token)

    # 3. Exception Handlers
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
    async def project_not_found(request: Request, exc: ProjectNotFound) -> JSONResponse:
        return JSONResponse(
            status_code=404 if exc.code == "project_missing" else 409,
            content={"detail": str(exc), "code": exc.code},
        )

    @app.exception_handler(DocumentNotFound)
    async def document_not_found(request: Request, exc: DocumentNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "No se encontró el documento."})

    @app.exception_handler(DatasetNotFound)
    async def dataset_not_found(request: Request, exc: DatasetNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "No se encontró el dataset."})

    @app.exception_handler(InvalidDataset)
    async def invalid_dataset(request: Request, exc: InvalidDataset) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(InvalidDocument)
    async def invalid_document(request: Request, exc: InvalidDocument) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    # 4. Service Tree Construction
    sources = SourceService(
        projects,
        SourceRepository(
            db_path,
            datasets_path.with_name(datasets_path.name + "-sources-v2"),
        ),
        DatasetLimits(
            max_bytes=10 * 1024 * 1024,
            max_rows=50000,
            max_columns=200,
            preview_rows=20,
            max_zip_bytes=50 * 1024 * 1024,
        ),
    )
    app.state.source_service = sources
    app.include_router(create_source_router(sources))

    workspace = WorkspaceService(sources, WorkspaceRepository(db_path))
    app.state.data_workspace_service = workspace
    app.include_router(create_workspace_router(workspace))

    evidence_store = SQLiteEvidenceStore(db_path)
    contexts = SQLiteContextRepository(db_path)
    instruments_v2 = InstrumentServiceV2(workspace, contexts)
    scores_v2 = ScoreServiceV2(instruments_v2)
    workspace.score_reader = scores_v2
    app.state.instruments_v2 = instruments_v2
    app.state.scores_v2 = scores_v2
    app.include_router(create_instrument_v2_router(instruments_v2, scores_v2))

    intents = IntentService(workspace, evidence_store, contexts)
    diagnostics = DiagnosticService(intents, workspace, evidence_store, instruments_v2)
    app.state.intent_service = intents
    app.state.diagnostic_service = diagnostics
    app.include_router(create_diagnostic_router(intents, diagnostics))

    analysis_v2 = AnalysisServiceV2(diagnostics, contexts)
    app.state.analysis_v2 = analysis_v2
    app.include_router(create_analysis_v2_router(analysis_v2))

    app.include_router(
        create_context_router(
            ContextService(
                projects,
                SQLiteContextRepository(db_path),
                actor_ref="production",
            )
        )
    )

    document_repository = SQLiteDocumentRepository(db_path, documents_path)
    documents = DocumentService(document_repository, projects)

    dataset_repository = SQLiteDatasetRepository(db_path, datasets_path)
    datasets = DatasetService(
        dataset_repository,
        projects,
        DatasetLimits(
            max_bytes=10 * 1024 * 1024,
            max_rows=50000,
            max_columns=200,
            preview_rows=20,
            max_zip_bytes=50 * 1024 * 1024,
        ),
    )

    extraction = ExtractionService(
        document_repository,
        document_repository,
        projects,
        ExtractionLimits(
            max_pages=100,
            max_units=10000,
            max_characters=200000,
            max_content_bytes=20 * 1024 * 1024,
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
                datasets, SQLiteEDARepository(db_path), ExploratoryAnalyzer()
            )
        )
    )

    default_ai_provider = (
        GeminiLanguageModel(settings)
        if getattr(settings, "gemini_api_key", "").strip()
        else CloudflareLanguageModel(settings)
    )

    methodology_repository = SQLiteMethodologyRepository(db_path)
    methodology = MethodologyService(
        extraction,
        methodology_repository,
        default_ai_provider,
        MethodologyLimits(
            max_characters=6000,
            max_input_tokens=16000,
            timeout_seconds=45,
            max_attempts=3,
            retry_seconds=30,
        ),
    )
    reviews = ReviewService(methodology, methodology_repository)
    app.include_router(create_methodology_router(methodology, reviews))

    packages = PackageService(
        projects,
        documents,
        reviews,
        datasets,
        SQLitePackageRepository(db_path),
    )
    app.include_router(create_package_router(packages))

    instrument_repository = SQLiteInstrumentRepository(db_path)
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

    extraction_service_inst = InstrumentExtractionService(
        projects=projects,
        documents=documents,
        extraction_service=extraction,
        provider=default_ai_provider,
        instrument_service=instruments,
        methodology=methodology_repository,
        integrity_secret=None,
    )
    app.state.instrument_extraction_service = extraction_service_inst
    app.include_router(create_instrument_router(instruments, extraction_service_inst))

    bridge = ResearchStatisticsBridge(
        projects, packages, datasets, instruments=instruments, instrument_reader=instrument_reader
    )
    analysis_service = ResearchAnalysisService(
        bridge,
        SQLiteAnalysisRepository(db_path),
        document_repository,
    )
    app.state.research_statistics_bridge = bridge
    app.state.research_analysis = analysis_service
    app.include_router(create_statistics_router(analysis_service))

    context_builder = ResearchContextBuilder(
        projects,
        documents,
        methodology_repository,
        datasets,
        EDAService(datasets, SQLiteEDARepository(db_path), ExploratoryAnalyzer()),
        packages,
        analysis_service,
        SQLitePreparationRepository(dataset_repository),
    )
    conversations = ConversationService(
        projects,
        SQLiteConversationRepository(db_path),
        default_ai_provider,
        ConversationSettings(),
        context_builder,
    )
    app.include_router(create_conversation_router(conversations))

    tutor = TutorService(
        conversations, analysis_v2, ContextService(projects, contexts, actor_ref="production")
    )
    app.state.tutor = tutor
    app.state.reports_v2 = ReportsServiceV2(analysis_v2, tutor)
    app.include_router(create_tutor_router(tutor, app.state.reports_v2))

    agentic_service = AgenticChatService(
        db_path,
        settings,
        sources,
        tutor,
        app.state.reports_v2,
    )
    app.state.agentic_service = agentic_service
    app.include_router(create_agentic_router(agentic_service))

    # 5. Public Health Checks
    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "tesisstat-api",
            "version": "0.1.0",
        }

    @app.get("/api/health")
    def api_health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "tesisstat-api",
            "version": "0.1.0",
            "environment": settings.app_env,
            "ai_configured": bool(settings.gemini_api_key and settings.gemini_api_key.strip()),
            "ai_provider": "gemini" if settings.gemini_api_key else "fallback",
            "persistence": "database_url" if settings.database_url else "sqlite_storage",
        }

    return app
