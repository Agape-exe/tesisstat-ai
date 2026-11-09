from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.modules.research.projects.models import Project, ProjectDraft, ProjectUpdate
from app.modules.research.projects.repository import ProjectRepository


class ProjectNotFound(Exception):
    pass


class ProjectService:
    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository

    def create(self, draft: ProjectDraft) -> Project:
        now = datetime.now(UTC)
        project = Project(**draft.model_dump(), id=uuid4(), created_at=now, updated_at=now)
        self.repository.add(project)
        return project

    def list(self) -> list[Project]:
        return self.repository.list()

    def get(self, project_id: UUID) -> Project:
        project = self.repository.get(project_id)
        if project is None:
            raise ProjectNotFound
        return project

    def update(self, project_id: UUID, draft: ProjectUpdate | ProjectDraft) -> Project:
        previous = self.get(project_id)
        project = Project(
            **{
                **previous.model_dump(),
                **draft.model_dump(exclude_unset=True),
                "updated_at": datetime.now(UTC),
            },
        )
        if not self.repository.replace(project):
            raise ProjectNotFound
        return project

    def delete(self, project_id: UUID) -> None:
        if not self.repository.delete(project_id):
            raise ProjectNotFound
