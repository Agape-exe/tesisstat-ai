"""Loopback-only synthetic integration API, mounted only in Research's dev app."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.modules.statistics.reports import render_docx, render_pdf
from app.orchestration.analysis_models import AnalysisRecord, ApprovalRequest, PlanRequest
from app.orchestration.analysis_service import ResearchAnalysisService
from app.shared.contracts import AnalysisResult


def local_only(request: Request) -> None:
    if (
        not request.client
        or request.client.host not in {"127.0.0.1", "::1", "testclient"}
        or request.url.hostname not in {"127.0.0.1", "localhost", "::1", "testserver"}
    ):
        raise HTTPException(403, "La integración de desarrollo solo está disponible en localhost.")


def create_router(service: ResearchAnalysisService) -> APIRouter:
    router = APIRouter(
        prefix="/api/research/projects/{project_id}/analysis",
        tags=["Research analysis (local synthetic development)"],
        dependencies=[Depends(local_only)],
    )

    @router.post("/plan", response_model=AnalysisRecord, status_code=201)
    def propose(project_id: UUID, body: PlanRequest) -> AnalysisRecord:
        return service.propose(project_id, body)

    @router.get("/plans", response_model=list[AnalysisRecord])
    def plans(project_id: UUID) -> list[AnalysisRecord]:
        return service.list(project_id)

    @router.post("/plans/{plan_id}/approve", response_model=AnalysisRecord)
    def approve(project_id: UUID, plan_id: str, body: ApprovalRequest) -> AnalysisRecord:
        return service.approve(project_id, plan_id, body)

    @router.post("/plans/{plan_id}/execute", response_model=AnalysisResult)
    def execute(project_id: UUID, plan_id: str) -> AnalysisResult:
        return service.execute(project_id, plan_id)

    @router.get("/results", response_model=list[AnalysisRecord])
    def results(project_id: UUID) -> list[AnalysisRecord]:
        return [record for record in service.list(project_id) if record.result is not None]

    @router.get("/plans/{plan_id}/results/{result_id}/report.{format}")
    def report(
        project_id: UUID, plan_id: UUID, result_id: str, format: Literal["docx", "pdf"]
    ) -> Response:
        record = service.completed_report(project_id, str(plan_id), result_id)
        context = (
            f"Proyecto: {project_id}",
            f"Investigación: {record.package.title}",
            f"Paquete: {record.plan.research_package_id}",
            f"Plan: {record.plan.id}",
            f"Dataset: {record.result.dataset_id}",
            f"Técnica: {record.plan.technique}",
            f"Justificación: {record.plan.rationale}",
            f"Aprobación explícita: {record.approved_at.isoformat()}",
            "Demostración local con datos sintéticos. No implica significancia estadística.",
        )
        renderer = render_docx if format == "docx" else render_pdf
        media = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if format == "docx"
            else "application/pdf"
        )
        return Response(
            renderer(record.result, context=context),
            media_type=media,
            headers={
                "Content-Disposition": f'attachment; filename="analysis-{plan_id}.{format}"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
