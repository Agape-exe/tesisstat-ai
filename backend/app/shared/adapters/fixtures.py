"""Explicit offline test doubles. Never mounted as production endpoints."""

from pathlib import Path

from app.shared.contracts import AnalysisPlan, AnalysisResult, ResearchPackage


class FixtureResearchReader:
    def __init__(self, path: Path) -> None:
        self.package = ResearchPackage.model_validate_json(path.read_text(encoding="utf-8"))

    def get_package(self, package_id: str) -> ResearchPackage:
        if package_id != self.package.id:
            raise KeyError(package_id)
        return self.package.model_copy(deep=True)


class FixtureAnalysisPlanner:
    def __init__(self, path: Path) -> None:
        self.plan = AnalysisPlan.model_validate_json(path.read_text(encoding="utf-8"))

    def propose(self, package: ResearchPackage, hypothesis_id: str) -> AnalysisPlan:
        if package.id != self.plan.research_package_id or hypothesis_id != self.plan.hypothesis_id:
            raise ValueError("Fixture plan does not match this research hypothesis")
        return self.plan.model_copy(deep=True)


class FixtureStatisticalEngine:
    def __init__(self, path: Path) -> None:
        self.result = AnalysisResult.model_validate_json(path.read_text(encoding="utf-8"))

    def execute(self, plan: AnalysisPlan) -> AnalysisResult:
        if plan.id != self.result.analysis_plan_id or plan.dataset_id != self.result.dataset_id:
            raise ValueError("Fixture result does not match this analysis plan")
        return self.result.model_copy(deep=True)
