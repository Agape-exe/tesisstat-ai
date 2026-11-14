from uuid import UUID

from fastapi import APIRouter

from app.modules.research.eda.sqlite_repository import EDAReport
from app.modules.research.eda.use_cases import EDAService


def create_router(service: EDAService) -> APIRouter:
    router = APIRouter(
        prefix="/api/research/projects/{project_id}/datasets/{dataset_id}/eda",
        tags=["Research EDA (development)"],
    )

    @router.post("", response_model=EDAReport)
    def run_eda(project_id: UUID, dataset_id: UUID, force: bool = False) -> EDAReport:
        return service.run(project_id, dataset_id, force)

    @router.get("", response_model=EDAReport)
    def get_eda(project_id: UUID, dataset_id: UUID) -> EDAReport:
        return service.get(project_id, dataset_id)

    return router
