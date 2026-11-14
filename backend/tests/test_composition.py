from uuid import UUID, uuid4

from app.modules.statistics.composition import build_engine
from app.shared.contracts import AnalysisPlan, DatasetReference


class FakeDatasetService:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls: list[tuple[UUID, UUID]] = []

    def read(self, project_id: UUID, dataset_id: UUID) -> bytes:
        self.calls.append((project_id, dataset_id))
        return self.payload


def test_composition_reads_only_through_authorized_dataset_service() -> None:
    project_id = uuid4()
    dataset_id = uuid4()
    service = FakeDatasetService(b"score,group\n1,A\n2,B\n")
    reference = DatasetReference(
        schema_version="1.0.0",
        id=str(dataset_id),
        location="opaque://not-a-filesystem-path",
        format="csv",
        row_count=2,
        columns=["score", "group"],
        synthetic=False,
    )
    engine = build_engine(service, project_id, {reference.id: reference})
    plan = AnalysisPlan(
        schema_version="1.0.0",
        id="plan-composition",
        research_package_id="package",
        hypothesis_id="hypothesis",
        dataset_id=reference.id,
        status="approved",
        technique="descriptive_summary",
        rationale="Validar la composición controlada.",
    )

    result = engine.execute(plan)

    assert result.status == "completed"
    assert service.calls == [(project_id, dataset_id)]
