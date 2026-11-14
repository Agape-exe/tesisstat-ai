from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.research.methodology.models import MethodologyReview, MethodologyState


class MethodologyRepository(Protocol):
    def get(self, project_id: UUID, document_id: UUID) -> MethodologyState | None: ...
    def claim(
        self,
        project_id: UUID,
        document_id: UUID,
        now: datetime,
        lease: datetime,
        max_attempts: int,
    ) -> tuple[MethodologyState, bool]: ...
    def save(self, result: MethodologyState) -> None: ...
    def get_review(self, project_id: UUID, document_id: UUID) -> MethodologyReview | None: ...
    def save_review(self, review: MethodologyReview, expected_version: int | None) -> bool: ...
