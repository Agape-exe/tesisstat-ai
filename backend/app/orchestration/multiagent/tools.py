"""Narrow read/planning ports. No engine, approval or mutation capabilities."""

from typing import Protocol
from uuid import UUID

from fastapi import HTTPException

from app.modules.conversation.context import normalize
from app.modules.conversation.research_context import ResearchContext, ResearchContextBuilder, clean
from app.modules.statistics.planner import DeterministicStatisticalPlanner
from app.orchestration.analysis_inputs import (
    ancova_questions,
    categorical_association_questions,
    independent_questions,
    multiple_regression_questions,
    paired_questions,
    pearson_questions,
    simple_regression_questions,
    spearman_questions,
)
from app.orchestration.research_statistics import ResearchInputError


class ResearchReader(Protocol):
    def build(self, project_id: UUID) -> ResearchContext: ...


class PlanningReader(Protocol):
    def inspect(self, project_id: UUID, research: ResearchContext, content: str) -> dict: ...


def clarification(question: str) -> dict:
    return {"status": "needs_clarification", "pending_questions": [question], "executable": False}


class VerifiedPlanningReader:
    def __init__(self, context: ResearchContextBuilder):
        self.context = context
        self.planner = DeterministicStatisticalPlanner()

    def inspect(self, project_id: UUID, research: ResearchContext, content: str) -> dict:
        if research.project_id != project_id:
            return clarification("Las fuentes no corresponden al proyecto activo.")
        methodologies = [s for s in research.sources if s.kind == "methodology"]
        if len(methodologies) != 1 or methodologies[0].status != "confirmed":
            return clarification("Confirma una única metodología vigente en la revisión humana.")
        source = next((s for s in research.sources if s.kind == "package"), None)
        if source is None or source.status != "current":
            return clarification(
                "Genera o actualiza el ResearchPackage después de revisar sus fuentes."
            )
        try:
            package = self.context.analyses.bridge.get_package(project_id, source.id)
        except (ResearchInputError, HTTPException, OSError):
            return clarification("El ResearchPackage ya no es verificable; revisa las fuentes.")
        dataset = next((s for s in research.sources if s.kind == "dataset"), None)
        # Re-read source versions to detect changes between Research and Planning.
        if (
            dataset is None
            or dataset.status != "current"
            or dataset.id != package.dataset.id
            or self.context.build(project_id).fingerprint != research.fingerprint
        ):
            return clarification(
                "Las fuentes cambiaron durante la consulta; actualiza e intenta otra vez."
            )
        candidates = [
            h
            for h in package.hypotheses
            if normalize(h.id) in normalize(content) or normalize(h.statement) in normalize(content)
        ]
        if not candidates and len(package.hypotheses) == 1:
            candidates = package.hypotheses
        if len(candidates) != 1:
            return clarification(
                "Indica el identificador o el texto de una única hipótesis vigente."
            )
        if package.design == "unknown" or package.observations == "unknown":
            return clarification("Confirma el diseño y la relación entre las observaciones.")
        plan = self.planner.propose(package, candidates[0].id)
        validate = {
            "pearson": pearson_questions,
            "spearman": spearman_questions,
            "chi_square": categorical_association_questions,
            "t_paired": paired_questions,
            "wilcoxon": paired_questions,
            "t_independent": independent_questions,
            "mann_whitney": independent_questions,
            "ancova": ancova_questions,
            "linear_regression_simple": simple_regression_questions,
            "linear_regression_multiple": multiple_regression_questions,
        }.get(plan.technique)
        if validate:
            questions = validate(package, candidates[0].id)
            if questions:
                plan.status = "needs_clarification"
                plan.pending_questions.extend(questions)
        # Only a preview. Persisting/approving/executing remains outside this port.
        return clean(
            {
                "status": plan.status,
                "scope": "orientative_not_persisted",
                "hypothesis_id": plan.hypothesis_id,
                "variable_ids": candidates[0].variable_ids,
                "technique": plan.technique,
                "rationale": plan.rationale,
                "assumptions_to_check": plan.assumptions_to_check,
                "pending_questions": plan.pending_questions,
                "executable": False,
                "approval_required": True,
            }
        )
