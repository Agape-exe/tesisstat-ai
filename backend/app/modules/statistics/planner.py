"""Deterministic Statistical Planner for the v1 research contracts."""

from __future__ import annotations

from app.shared.contracts import (
    AnalysisPlan,
    ResearchHypothesis,
    ResearchPackage,
    ResearchVariable,
)

from .catalog import get_technique


class UnknownHypothesis(ValueError):
    """Raised when a plan is requested for a hypothesis outside the package."""


class DeterministicStatisticalPlanner:
    """Propose an allowlisted technique without an LLM or numerical execution."""

    def propose(self, package: ResearchPackage, hypothesis_id: str) -> AnalysisPlan:
        hypothesis = next((item for item in package.hypotheses if item.id == hypothesis_id), None)
        if hypothesis is None:
            raise UnknownHypothesis(f"Hipótesis desconocida: {hypothesis_id}")

        base = {
            "id": f"plan-{package.id}-{hypothesis.id}",
            "schema_version": "1.0.0",
            "research_package_id": package.id,
            "hypothesis_id": hypothesis.id,
            "dataset_id": package.dataset.id,
            "alpha": 0.05,
        }
        if package.methodology_status != "reviewed":
            return self._clarification(
                base,
                "La metodología debe estar revisada por una persona antes de proponer una prueba.",
                ["Confirma la revisión metodológica antes de planificar el análisis."],
            )

        variables = self._variables_for(package, hypothesis)
        if hypothesis.kind == "descriptive":
            return self._proposed(base, "descriptive_summary")
        if hypothesis.kind == "association":
            return self._plan_association(base, variables)
        if hypothesis.kind == "comparison":
            return self._plan_comparison(base, package, variables)
        if hypothesis.kind == "prediction":
            return self._plan_prediction(base, variables)
        return self._clarification(
            base,
            "El tipo de hipótesis no permite seleccionar una técnica de forma segura.",
            ["Indica si la hipótesis es descriptiva, de asociación, comparación o predicción."],
        )

    @staticmethod
    def _variables_for(
        package: ResearchPackage, hypothesis: ResearchHypothesis
    ) -> list[ResearchVariable]:
        by_id = {variable.id: variable for variable in package.variables}
        return [by_id[variable_id] for variable_id in hypothesis.variable_ids]

    def _plan_association(
        self, base: dict[str, object], variables: list[ResearchVariable]
    ) -> AnalysisPlan:
        if len(variables) != 2:
            return self._clarification(
                base,
                "Una asociación requiere exactamente dos variables.",
                ["Selecciona exactamente dos variables para la hipótesis."],
            )
        scales = {variable.measurement_scale for variable in variables}
        if scales <= {"interval", "ratio"}:
            return self._proposed(base, "pearson")
        if scales <= {"nominal", "ordinal"} and "ordinal" not in scales:
            return self._proposed(base, "chi_square")
        if "unknown" in scales:
            return self._clarification(
                base,
                "No se conocen las escalas de medición de ambas variables.",
                ["Confirma la escala de medición de cada variable."],
            )
        return self._proposed(base, "spearman")

    def _plan_comparison(
        self,
        base: dict[str, object],
        package: ResearchPackage,
        variables: list[ResearchVariable],
    ) -> AnalysisPlan:
        dependent = [variable for variable in variables if variable.role == "dependent"]
        if len(dependent) != 1:
            return self._clarification(
                base,
                "La comparación requiere una única variable dependiente identificada.",
                ["Marca exactamente una variable como dependiente."],
            )
        scale = dependent[0].measurement_scale
        if scale not in {"interval", "ratio", "ordinal"}:
            return self._clarification(
                base,
                "La escala de la variable dependiente no permite elegir una comparación.",
                [
                    (
                        "Confirma una escala ordinal, intervalar o de razón para la "
                        "variable dependiente."
                    )
                ],
            )
        if package.observations in {"paired", "repeated"}:
            technique = "t_paired" if scale in {"interval", "ratio"} else "wilcoxon"
            return self._proposed(base, technique)
        if package.observations == "independent":
            technique = "t_independent" if scale in {"interval", "ratio"} else "mann_whitney"
            return self._clarification(
                base,
                (
                    "La comparación independiente necesita conocer la cantidad de grupos "
                    "antes de elegir la prueba."
                ),
                [
                    "Indica si la variable de agrupación tiene dos grupos o tres o más.",
                    (
                        f"Para dos grupos se evaluará {get_technique(technique).label}; "
                        "para más grupos se evaluará ANOVA o Kruskal–Wallis."
                    ),
                ],
            )
        return self._clarification(
            base,
            "No se conoce si las observaciones son independientes o emparejadas.",
            ["Confirma la relación entre las observaciones."],
        )

    def _plan_prediction(
        self, base: dict[str, object], variables: list[ResearchVariable]
    ) -> AnalysisPlan:
        dependent = [variable for variable in variables if variable.role == "dependent"]
        predictors = [
            variable for variable in variables if variable.role in {"independent", "covariate"}
        ]
        if len(dependent) != 1 or not predictors:
            return self._clarification(
                base,
                "La predicción requiere una dependiente y al menos un predictor.",
                ["Identifica una variable dependiente y uno o más predictores."],
            )
        if dependent[0].measurement_scale not in {"interval", "ratio"} or any(
            variable.measurement_scale not in {"interval", "ratio"} for variable in predictors
        ):
            return self._clarification(
                base,
                (
                    "La regresión lineal requiere variables cuantitativas con escala "
                    "intervalar o de razón."
                ),
                ["Confirma las escalas de la variable dependiente y de los predictores."],
            )
        technique = (
            "linear_regression_simple" if len(predictors) == 1 else "linear_regression_multiple"
        )
        return self._proposed(base, technique)

    @staticmethod
    def _proposed(base: dict[str, object], technique_name: str) -> AnalysisPlan:
        technique = get_technique(technique_name)
        return AnalysisPlan(
            **base,
            status="proposed",
            technique=technique.name,
            rationale=technique.rationale,
            assumptions_to_check=list(technique.assumptions_to_check),
        )

    @staticmethod
    def _clarification(
        base: dict[str, object], rationale: str, questions: list[str]
    ) -> AnalysisPlan:
        return AnalysisPlan(
            **base,
            status="needs_clarification",
            technique=None,
            rationale=rationale,
            pending_questions=questions,
        )
