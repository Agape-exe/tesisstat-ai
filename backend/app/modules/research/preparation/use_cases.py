import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.modules.research.datasets.models import Dataset, DatasetPreview
from app.modules.research.datasets.use_cases import DatasetService
from app.modules.research.preparation.engine import RULE_VERSION, transform
from app.modules.research.preparation.models import (
    ApplyRequest,
    Plan,
    PreparationPreview,
    PreparationRecord,
)
from app.modules.research.preparation.repository import PreparationRepository


class PreviewConflict(Exception):
    pass


class PreparationService:
    def __init__(self, datasets: DatasetService, repository: PreparationRepository) -> None:
        self.datasets = datasets
        self.repository = repository

    @staticmethod
    def _hash(plan: Plan) -> str:
        return hashlib.sha256(plan.model_dump_json().encode()).hexdigest()

    def preview(self, project_id: UUID, source_id: UUID, plan: Plan) -> PreparationPreview:
        source = self.datasets.get(project_id, source_id)
        data = self.datasets.read(project_id, source_id)
        result = transform(data, source.format, plan, self.datasets.limits)
        preview_id = uuid4()
        digest = hashlib.sha256(data).hexdigest()
        plan_hash = self._hash(plan)
        expires_at = datetime.now(UTC) + timedelta(minutes=15)
        self.repository.save_preview(
            preview_id, project_id, source_id, plan_hash, digest, expires_at.isoformat()
        )
        return PreparationPreview(
            preview_id=preview_id,
            plan_hash=plan_hash,
            source_sha256=digest,
            rule_version=RULE_VERSION,
            expires_at=expires_at,
            original_rows=result["original_rows"],
            result_rows=len(result["rows"]),
            original_columns=result["original_columns"],
            result_columns=result["columns"],
            rows_removed=result["rows_removed"],
            cells_changed=result["cells_changed"],
            warnings=result["warnings"],
            rows=result["rows"][:20],
            operations=result["operations"],
        )

    def apply(self, project_id: UUID, source_id: UUID, request: ApplyRequest) -> PreparationRecord:
        self.datasets.get(project_id, source_id)
        stored = self.repository.get_preview(request.preview_id)
        if stored is None or stored[0] != str(project_id) or stored[1] != str(source_id):
            raise PreviewConflict("La vista previa no existe para este dataset.")
        plan_hash = self._hash(request.plan)
        if request.plan_hash != plan_hash or stored[2] != plan_hash:
            raise PreviewConflict("El plan cambió desde la vista previa.")
        existing = self.repository.get_result(request.preview_id)
        if existing:
            return existing
        if datetime.fromisoformat(stored[4]) < datetime.now(UTC):
            raise PreviewConflict("La vista previa venció; genera otra.")
        data = self.datasets.read(project_id, source_id)
        if hashlib.sha256(data).hexdigest() != stored[3]:
            raise PreviewConflict("El contenido fuente cambió desde la vista previa.")
        source = self.datasets.get(project_id, source_id)
        result = transform(data, source.format, request.plan, self.datasets.limits)
        result_id = uuid4()
        name = f"preparado-{result_id.hex[:8]}.csv"
        dataset = Dataset(
            id=result_id,
            project_id=project_id,
            name=name,
            format="csv",
            size=len(result["data"]),
            row_count=len(result["rows"]),
            column_count=len(result["columns"]),
            columns=result["columns"],
            uploaded_at=datetime.now(UTC),
            warnings=result["warnings"],
            source_dataset_id=source_id,
            synthetic=source.synthetic,
        )
        preview = DatasetPreview(
            columns=result["columns"],
            rows=result["rows"][:20],
            row_count=len(result["rows"]),
            column_count=len(result["columns"]),
            format="csv",
            warnings=result["warnings"],
        )
        record = PreparationRecord(
            preview_id=request.preview_id,
            project_id=project_id,
            source_id=source_id,
            result_id=result_id,
            prepared_at=dataset.uploaded_at,
            plan=request.plan,
            source_sha256=stored[3],
            rule_version=RULE_VERSION,
            original_rows=result["original_rows"],
            result_rows=len(result["rows"]),
            original_columns=result["original_columns"],
            result_columns=result["columns"],
            rows_removed=result["rows_removed"],
            cells_changed=result["cells_changed"],
            warnings=result["warnings"],
            operations=result["operations"],
        )
        return self.repository.apply(record, dataset, preview, result["data"])

    def list(self, project_id: UUID, source_id: UUID) -> list[PreparationRecord]:
        self.datasets.get(project_id, source_id)
        return self.repository.list(project_id, source_id)
