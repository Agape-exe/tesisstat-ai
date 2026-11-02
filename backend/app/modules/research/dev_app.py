"""Independent, unauthenticated development app. Never deploy with student data."""

import logging
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import Settings
from app.modules.research.projects.repository import ProjectRepository
from app.modules.research.projects.routes import create_router
from app.modules.research.projects.sqlite_repository import SQLiteProjectRepository
from app.modules.research.projects.use_cases import ProjectNotFound, ProjectService

logger = logging.getLogger(__name__)


class ResearchDevSettings(Settings):
    research_db_path: Path = Path(".cache/research/projects.sqlite3")


def create_app(
    repository: ProjectRepository | None = None, settings: ResearchDevSettings | None = None
) -> FastAPI:
    settings = settings or ResearchDevSettings()
    if repository is None:
        repository = SQLiteProjectRepository(settings.research_db_path)
    app = FastAPI(title="TesisStat Research — development only", version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )

    @app.exception_handler(ProjectNotFound)
    async def not_found(request: Request, exc: ProjectNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "No se encontró el proyecto."})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = {}
        for error in exc.errors():
            field = str(error["loc"][-1])
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
            content={"detail": "Revisa los datos del proyecto.", "errors": errors},
        )

    @app.exception_handler(sqlite3.Error)
    async def storage_error(request: Request, exc: sqlite3.Error) -> JSONResponse:
        logger.error("Research development storage failed", exc_info=exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "El almacenamiento local no está disponible. Intenta nuevamente."},
        )

    app.include_router(create_router(ProjectService(repository)))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "research-dev", "version": "0.2.0"}

    return app


app = create_app()
