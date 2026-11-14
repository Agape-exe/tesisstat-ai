from uuid import UUID

from fastapi import APIRouter, Response, status

from app.modules.research.datasets.use_cases import DatasetService
from app.modules.research.documents.use_cases import DocumentService
from app.modules.research.projects.models import Project, ProjectDraft, ProjectUpdate
from app.modules.research.projects.use_cases import ProjectService


def create_router(
    service: ProjectService,
    documents: DocumentService | None = None,
    datasets: DatasetService | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/research/projects", tags=["Research projects (development)"])

    @router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
    def create_project(draft: ProjectDraft, response: Response) -> Project:
        project = service.create(draft)
        response.headers["Location"] = f"/api/research/projects/{project.id}"
        return project

    @router.get("", response_model=list[Project])
    def list_projects() -> list[Project]:
        return service.list()

    @router.get("/{project_id}", response_model=Project)
    def get_project(project_id: UUID) -> Project:
        return service.get(project_id)

    @router.put("/{project_id}", response_model=Project)
    def update_project(project_id: UUID, draft: ProjectUpdate) -> Project:
        """Preserve omitted fields; explicit null clears nullable academic fields."""
        return service.update(project_id, draft)

    @router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_project(project_id: UUID) -> Response:
        if datasets is not None:
            service.get(project_id)
            for dataset in datasets.list(project_id):
                datasets.delete(project_id, dataset.id)
        if documents is not None:
            service.get(project_id)
            for document in documents.list(project_id):
                documents.delete(project_id, document.id)
        service.delete(project_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
