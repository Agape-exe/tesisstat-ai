from typing import Protocol

from app.shared.contracts import AnalysisPlan, AnalysisResult, ResearchPackage


class AnalysisPlanner(Protocol):
    def propose(self, package: ResearchPackage, hypothesis_id: str) -> AnalysisPlan: ...


class StatisticalEngine(Protocol):
    """Only deterministic, allowlisted Python operations may implement this port."""

    def execute(self, plan: AnalysisPlan) -> AnalysisResult: ...
