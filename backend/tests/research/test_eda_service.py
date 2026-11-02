from pathlib import Path
from uuid import uuid4

from app.modules.research.datasets.readers import DatasetLimits
from app.modules.research.eda.analyzer import ExploratoryAnalyzer
from app.modules.research.eda.sqlite_repository import SQLiteEDARepository
from app.modules.research.eda.use_cases import EDANotFound, EDAService


class FakeDatasets:
    limits = DatasetLimits()
    format = "csv"
    data = b"A,B\n1,x\n1,x\n"

    def get(self, project_id, dataset_id):
        return self

    def read(self, project_id, dataset_id):
        return self.data


def test_report_cache_restart_invalidation_and_force(tmp_path: Path):
    datasets = FakeDatasets()
    repository = SQLiteEDARepository(tmp_path / "eda.sqlite3")
    service = EDAService(datasets, repository, ExploratoryAnalyzer())
    project_id, dataset_id = uuid4(), uuid4()
    first = service.run(project_id, dataset_id)
    assert first.summary["duplicates"] == 1
    assert service.run(project_id, dataset_id).processed_at == first.processed_at
    restarted = EDAService(
        datasets, SQLiteEDARepository(tmp_path / "eda.sqlite3"), ExploratoryAnalyzer()
    )
    assert restarted.get(project_id, dataset_id) == first
    datasets.data = b"A,B\n2,y\n"
    try:
        restarted.get(project_id, dataset_id)
    except EDANotFound:
        pass
    else:
        raise AssertionError("Stale report was returned")
    changed = restarted.run(project_id, dataset_id)
    assert changed.summary["rows"] == 1
    assert changed.content_sha256 != first.content_sha256
    assert restarted.run(project_id, dataset_id, force=True).summary == changed.summary
