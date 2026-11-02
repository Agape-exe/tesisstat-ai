"""Development-only API for the descriptive statistics demonstration."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.shared.contracts import AnalysisPlan, AnalysisResult, DatasetReference

from .datasets import fixture_catalog, list_profiles, read_csv_dataset
from .descriptive import describe_column
from .engine import DeterministicStatisticalEngine
from .reports import render_docx, render_pdf, render_text
from .research_bridge import BytesDatasetReader


class DescriptiveRequest(BaseModel):
    columns: list[str] = Field(min_length=1, max_length=20)


def _fixture_reference(definition, data: dict[str, list[str | None]]) -> DatasetReference:
    columns = list(data)
    row_count = len(data[columns[0]]) if columns else 0
    return DatasetReference(
        schema_version="1.0.0",
        id=definition.id,
        location=f"opaque://fixture/{definition.id}",
        format="csv",
        row_count=row_count,
        columns=columns,
        synthetic=True,
    )


def create_descriptive_app(root: Path | None = None) -> FastAPI:
    app = FastAPI(title="TesisStat AI — Descriptivos", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
    catalog = fixture_catalog(root)

    def definition_or_404(dataset_id: str):
        definition = catalog.get(dataset_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Dataset de demostración no encontrado.")
        return definition

    @app.get("/datasets")
    def datasets() -> list[dict[str, str]]:
        return [{"id": item.id, "label": item.label} for item in catalog.values()]

    @app.get("/datasets/{dataset_id}/columns")
    def columns(dataset_id: str) -> list[dict[str, object]]:
        try:
            return [asdict(profile) for profile in list_profiles(definition_or_404(dataset_id))]
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/datasets/{dataset_id}/descriptive")
    def descriptive(dataset_id: str, request: DescriptiveRequest) -> list[dict[str, object]]:
        try:
            data = read_csv_dataset(definition_or_404(dataset_id))
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        unknown = sorted(set(request.columns) - set(data))
        if unknown:
            raise HTTPException(
                status_code=422, detail=f"Columnas desconocidas: {', '.join(unknown)}"
            )
        return [asdict(describe_column(name, data[name])) for name in request.columns]

    @app.get("/datasets/{dataset_id}/plan")
    def plan(dataset_id: str) -> dict[str, object]:
        definition = definition_or_404(dataset_id)
        try:
            reference = _fixture_reference(definition, read_csv_dataset(definition))
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return AnalysisPlan(
            schema_version="1.0.0",
            id=f"demo-plan-{definition.id}",
            research_package_id="demo-package",
            hypothesis_id="descriptive-demo",
            dataset_id=reference.id,
            status="approved",
            technique="descriptive_summary",
            rationale="El dataset de demostración se resume antes de contrastar hipótesis.",
        ).model_dump()

    @app.post("/datasets/{dataset_id}/analysis")
    def analysis(dataset_id: str) -> dict[str, object]:
        definition = definition_or_404(dataset_id)
        try:
            data = read_csv_dataset(definition)
            reference = _fixture_reference(definition, data)
            reader = BytesDatasetReader(lambda _: definition.path.read_bytes())
            result = DeterministicStatisticalEngine(reader, {reference.id: reference}).execute(
                AnalysisPlan(
                    schema_version="1.0.0",
                    id=f"demo-plan-{definition.id}",
                    research_package_id="demo-package",
                    hypothesis_id="descriptive-demo",
                    dataset_id=reference.id,
                    status="approved",
                    technique="descriptive_summary",
                    rationale="El dataset de demostración se resume antes de contrastar hipótesis.",
                )
            )
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return result.model_dump()

    @app.get("/datasets/{dataset_id}/report")
    def report(
        dataset_id: str,
        format: str = Query(default="txt", pattern="^(txt|docx|pdf)$"),
    ) -> Response:
        """Render the completed demo result without accepting arbitrary code or paths."""
        try:
            result = AnalysisResult.model_validate(analysis(dataset_id))
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if result.status != "completed":
            raise HTTPException(status_code=422, detail="El análisis no está completado.")
        if format == "docx":
            return Response(
                content=render_docx(result),
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": f'attachment; filename="{dataset_id}-report.docx"'},
            )
        if format == "pdf":
            return Response(
                content=render_pdf(result),
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{dataset_id}-report.pdf"'},
            )
        return Response(
            content=render_text(result),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{dataset_id}-report.txt"'},
        )

    return app
