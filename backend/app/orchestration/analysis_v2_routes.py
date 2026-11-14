from fastapi import APIRouter

from app.shared.plans_v2 import (
    AnalysisPlanV2,
    AnalysisResultV2,
    ApprovalRequest,
    ExecutionRequest,
    PlanRequest,
)


def create_router(service):
    router = APIRouter(
        prefix="/api/v2/research/projects/{project_id}/analysis", tags=["analysis-v2"]
    )

    @router.post("/plans", response_model=AnalysisPlanV2, status_code=201)
    def propose(project_id: str, body: PlanRequest):
        return service.propose(project_id, body)

    @router.get("/plans", response_model=list[AnalysisPlanV2])
    def plans(project_id: str):
        return service.list(project_id)

    @router.get("/plans/{plan_id}", response_model=AnalysisPlanV2)
    def plan(project_id: str, plan_id: str):
        return service.get(project_id, plan_id)

    @router.post("/plans/{plan_id}/authorize-data", response_model=AnalysisPlanV2)
    def authorize(project_id: str, plan_id: str, body: ApprovalRequest):
        return service.authorize(project_id, plan_id, body)

    @router.post("/plans/{plan_id}/approve", response_model=AnalysisPlanV2)
    def approve(project_id: str, plan_id: str, body: ApprovalRequest):
        return service.approve(project_id, plan_id, body)

    @router.post("/plans/{plan_id}/execute", response_model=AnalysisResultV2)
    def execute(project_id: str, plan_id: str, body: ExecutionRequest):
        return service.execute(project_id, plan_id, body)

    @router.get("/plans/{plan_id}/attempts")
    def attempts(project_id: str, plan_id: str):
        return service.attempts(project_id, plan_id)

    @router.get("/results", response_model=list[AnalysisResultV2])
    def results(project_id: str):
        return service.results(project_id)

    @router.get("/results/{result_id}", response_model=AnalysisResultV2)
    def result(project_id: str, result_id: str):
        return service.result(project_id, result_id)

    return router
