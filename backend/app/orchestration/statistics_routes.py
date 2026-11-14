"""Compatibility routes: reuse the persisted Research approval workflow."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.orchestration.analysis_models import PlanRequest
from app.orchestration.analysis_routes import local_only
from app.orchestration.analysis_service import ResearchAnalysisService
from app.shared.contracts import AnalysisPlan, AnalysisResult


class StatisticsPlanRequest(BaseModel):
    package_id: str
    hypothesis_id: str


class StatisticsAnalysisRequest(StatisticsPlanRequest):
    # Accepted for old clients, but never grants approval or changes plan status.
    approve: bool = False
    plan_id: str | None = None


def create_statistics_router(service: ResearchAnalysisService) -> APIRouter:
    router = APIRouter(
        prefix="/api/research/projects/{project_id}/statistics",
        dependencies=[Depends(local_only)],
    )

    @router.post("/plan", response_model=AnalysisPlan)
    def propose(project_id: UUID, request: StatisticsPlanRequest) -> AnalysisPlan:
        return service.propose(project_id, PlanRequest(**request.model_dump())).plan

    @router.post("/analysis", response_model=AnalysisResult)
    def execute(project_id: UUID, request: StatisticsAnalysisRequest) -> AnalysisResult:
        service.bridge.projects.get(project_id)
        if not request.plan_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Usa un plan persistido y apruébalo con la acción independiente en "
                    "/analysis/plans/{plan_id}/approve. approve=true no concede aprobación."
                ),
            )
        record = next(
            (item for item in service.list(project_id) if item.plan.id == request.plan_id), None
        )
        if record is None:
            raise HTTPException(404, "No se encontró el plan en este proyecto.")
        if (
            record.plan.research_package_id != request.package_id
            or record.plan.hypothesis_id != request.hypothesis_id
        ):
            raise HTTPException(409, "El paquete o hipótesis no corresponde al plan persistido.")
        return service.execute(project_id, record.plan.id)

    return router
