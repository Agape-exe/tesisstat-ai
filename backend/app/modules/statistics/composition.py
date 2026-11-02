"""Composition helpers that connect Research's controlled dataset service."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from app.shared.contracts import DatasetReference

from .engine import DeterministicStatisticalEngine
from .research_bridge import BytesDatasetReader

if TYPE_CHECKING:
    from app.orchestration.research_statistics import ResearchStatisticsBridge
    from app.shared.contracts import ResearchPackage


class AuthorizedDatasetService(Protocol):
    def read(self, project_id: UUID, dataset_id: UUID) -> bytes: ...


def build_engine(
    datasets: AuthorizedDatasetService,
    project_id: UUID,
    references: Mapping[str, DatasetReference],
) -> DeterministicStatisticalEngine:
    """Build the engine using Research IDs, never storage paths from a client."""

    def load(reference: DatasetReference) -> bytes:
        return datasets.read(project_id, UUID(reference.id))

    return DeterministicStatisticalEngine(BytesDatasetReader(load), references)


def build_engine_from_research_bridge(
    bridge: ResearchStatisticsBridge,
    project_id: UUID,
    package: ResearchPackage,
) -> DeterministicStatisticalEngine:
    """Build an engine whose reads are revalidated by Research on every request."""

    def load(reference: DatasetReference) -> bytes:
        return bridge.read_dataset(project_id, package, reference)

    return DeterministicStatisticalEngine(
        BytesDatasetReader(load), {package.dataset.id: package.dataset}
    )
