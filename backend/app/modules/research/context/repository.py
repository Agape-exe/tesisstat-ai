from collections.abc import Callable
from typing import Protocol

from app.shared.analysis_v2 import ProjectContextV2


class ContextError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int = 422,
        fields: list[str] | None = None,
        current_revision: int | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status = status
        self.fields = fields or []
        self.current_revision = current_revision


class ContextRepository(Protocol):
    def get(self, project_id: str) -> ProjectContextV2 | None: ...

    def revisions(self, project_id: str) -> list[ProjectContextV2]: ...

    def append(
        self,
        project_id: str,
        expected_revision: int,
        build: Callable[[ProjectContextV2], ProjectContextV2],
    ) -> ProjectContextV2:
        """Compare and append a historical revision in one atomic transaction."""
        ...
