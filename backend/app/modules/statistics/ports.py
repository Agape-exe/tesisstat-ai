from typing import Protocol

from app.shared.contracts import AnalysisPlan, AnalysisResult, DatasetReference, ResearchPackage

from .datasets import DatasetTable


class DatasetReader(Protocol):
    """Read an authorized dataset without exposing storage paths to Statistics."""

    def read(self, reference: DatasetReference) -> DatasetTable: ...


class AnalysisPlanner(Protocol):
    def propose(self, package: ResearchPackage, hypothesis_id: str) -> AnalysisPlan: ...


class StatisticalEngine(Protocol):
    """Only deterministic, allowlisted Python operations may implement this port."""

    def execute(self, plan: AnalysisPlan) -> AnalysisResult: ...
