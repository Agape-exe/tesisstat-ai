from typing import Protocol
from uuid import UUID

from app.modules.research.datasets.models import Dataset, DatasetPreview
from app.modules.research.preparation.models import PreparationRecord


class PreparationRepository(Protocol):
    def save_preview(
        self,
        preview_id: UUID,
        project_id: UUID,
        source_id: UUID,
        plan_hash: str,
        source_sha256: str,
        expires_at: str,
    ) -> None: ...
    def get_preview(self, preview_id: UUID) -> tuple | None: ...
    def get_result(self, preview_id: UUID) -> PreparationRecord | None: ...
    def apply(
        self, record: PreparationRecord, dataset: Dataset, preview: DatasetPreview, data: bytes
    ) -> PreparationRecord: ...
    def list(self, project_id: UUID, source_id: UUID) -> list[PreparationRecord]: ...
