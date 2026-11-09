from collections.abc import Callable
from typing import Protocol

from app.modules.research.context.import_models import ContextSuggestion
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
    def create_suggestion(self, suggestion: ContextSuggestion) -> ContextSuggestion: ...

    def list_suggestions(self, project_id: str) -> list[ContextSuggestion]: ...

    def suggestion_operation(self, project_id, suggestion_id, operation, body=None, build=None): ...

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
