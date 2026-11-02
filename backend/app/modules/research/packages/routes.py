from uuid import UUID

from fastapi import APIRouter

from app.modules.research.packages.models import PackageConfiguration, ValidationStatus
from app.modules.research.packages.use_cases import PackageService
from app.shared.contracts import ResearchPackage


def create_router(service: PackageService) -> APIRouter:
    router = APIRouter(
        prefix="/api/research/projects/{project_id}/package",
        tags=["Research packages (development)"],
    )

    @router.get("/status", response_model=ValidationStatus)
    def status(project_id: UUID) -> ValidationStatus:
        return service.validate(project_id)

    @router.get("/configuration", response_model=PackageConfiguration)
    def configuration(project_id: UUID) -> PackageConfiguration:
        return service.configuration(project_id)

    @router.put("/configuration", response_model=PackageConfiguration)
    def save(project_id: UUID, configuration: PackageConfiguration) -> PackageConfiguration:
        return service.save(project_id, configuration)

    @router.post("/validate", response_model=ValidationStatus)
    def validate(project_id: UUID) -> ValidationStatus:
        return service.check(project_id)

    @router.post("/build", response_model=ResearchPackage)
    def build(project_id: UUID) -> ResearchPackage:
        return service.build(project_id)

    @router.get("", response_model=ResearchPackage)
    def get(project_id: UUID) -> ResearchPackage:
        return service.get_package(project_id)

    return router
