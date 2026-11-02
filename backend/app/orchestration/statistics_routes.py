"""HTTP orchestration for the authorized Research → Statistics flow."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.modules.statistics.composition import build_engine_from_research_bridge
from app.modules.statistics.planner import DeterministicStatisticalPlanner, UnknownHypothesis
from app.orchestration.research_statistics import ResearchInputError, ResearchStatisticsBridge
from app.shared.contracts import AnalysisPlan, AnalysisResult, ResearchPackage


class StatisticsPlanRequest(BaseModel):
    package_id: str
    hypothesis_id: str


class StatisticsAnalysisRequest(StatisticsPlanRequest):
    approve: bool = False


def create_statistics_router(bridge: ResearchStatisticsBridge) -> APIRouter:
    router = APIRouter(prefix="/api/research/projects/{project_id}/statistics")
    planner = DeterministicStatisticalPlanner()

    def package_and_plan(
        project_id: UUID, package_id: str, hypothesis_id: str
    ) -> tuple[ResearchPackage, AnalysisPlan]:
        try:
            package = bridge.get_package(project_id, package_id)
            plan = planner.propose(package, hypothesis_id)
        except ResearchInputError as error:
            status = 404 if error.code in {"project_missing", "package_missing"} else 409
            raise HTTPException(status_code=status, detail=str(error)) from error
        except UnknownHypothesis as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return package, plan

    @router.post("/plan", response_model=AnalysisPlan)
    def propose(project_id: UUID, request: StatisticsPlanRequest) -> AnalysisPlan:
        _, plan = package_and_plan(project_id, request.package_id, request.hypothesis_id)
        return plan

    @router.post("/analysis", response_model=AnalysisResult)
    def execute(project_id: UUID, request: StatisticsAnalysisRequest) -> AnalysisResult:
        package, plan = package_and_plan(project_id, request.package_id, request.hypothesis_id)
        if not request.approve:
            raise HTTPException(
                status_code=409,
                detail="El plan debe aprobarse explícitamente antes de ejecutar el análisis.",
            )
        approved = plan.model_copy(update={"status": "approved"})
        engine = build_engine_from_research_bridge(bridge, project_id, package)
        return engine.execute(approved)

    return router
