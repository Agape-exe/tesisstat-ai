import hashlib
from datetime import UTC, datetime
from uuid import UUID

from app.modules.research.datasets.use_cases import DatasetService
from app.modules.research.eda.analyzer import Analyzer
from app.modules.research.eda.sqlite_repository import EDAReport, SQLiteEDARepository


class EDANotFound(Exception):
    pass


class EDAService:
    def __init__(
        self, datasets: DatasetService, repository: SQLiteEDARepository, analyzer: Analyzer
    ) -> None:
        self.datasets = datasets
        self.repository = repository
        self.analyzer = analyzer

    def get(self, project_id: UUID, dataset_id: UUID) -> EDAReport:
        self.datasets.get(project_id, dataset_id)
        report = self.repository.get(project_id, dataset_id)
        if (
            report is None
            or report.rule_version != self.analyzer.version
            or report.content_sha256
            != hashlib.sha256(self.datasets.read(project_id, dataset_id)).hexdigest()
        ):
            raise EDANotFound
        return report

    def run(self, project_id: UUID, dataset_id: UUID, force: bool = False) -> EDAReport:
        dataset = self.datasets.get(project_id, dataset_id)
        data = self.datasets.read(project_id, dataset_id)
        digest = hashlib.sha256(data).hexdigest()
        existing = self.repository.get(project_id, dataset_id)
        if (
            existing
            and not force
            and existing.rule_version == self.analyzer.version
            and existing.content_sha256 == digest
        ):
            return existing
        result = self.analyzer.analyze(data, dataset.format, self.datasets.limits)
        report = EDAReport(
            project_id=project_id,
            dataset_id=dataset_id,
            processed_at=datetime.now(UTC).isoformat(),
            content_sha256=digest,
            **result,
        )
        self.repository.save(report)
        return report
