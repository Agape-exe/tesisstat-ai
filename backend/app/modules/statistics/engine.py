"""Deterministic execution of approved statistical analysis plans."""

from __future__ import annotations

from collections.abc import Mapping

from app.shared.contracts import (
    AnalysisPlan,
    AnalysisResult,
    AssumptionCheck,
    DatasetReference,
    Metric,
)

from .anova import anova, anova_welch, games_howell, tukey
from .assumptions import homogeneity, independence, normality
from .comparisons import t_independent, t_paired, t_welch
from .descriptive import DescriptiveResult
from .execution import AnalysisInput
from .inferential import (
    StatisticalCalculationError,
    TechniqueResult,
    chi_square,
    cronbach_alpha,
    fisher_exact,
    pearson,
    spearman,
)
from .nonparametric import kruskal_wallis, mann_whitney, wilcoxon
from .ports import DatasetReader
from .regression import ancova, linear_regression_multiple, linear_regression_simple
from .service import describe_table


class DeterministicStatisticalEngine:
    """Execute only techniques explicitly implemented by this engine version."""

    VERSION = "statistics-engine-v2.0.0"
    _IMPLEMENTED_TECHNIQUES = frozenset(
        {
            "descriptive_summary",
            "cronbach_alpha",
            "pearson",
            "spearman",
            "t_independent",
            "t_paired",
            "t_welch",
            "mann_whitney",
            "wilcoxon",
            "anova",
            "anova_welch",
            "kruskal_wallis",
            "tukey",
            "games_howell",
            "chi_square",
            "fisher_exact",
            "ancova",
            "linear_regression_simple",
            "linear_regression_multiple",
        }
    )

    def __init__(
        self,
        reader: DatasetReader,
        references: Mapping[str, DatasetReference],
        inputs: Mapping[str, AnalysisInput] | None = None,
    ) -> None:
        self._reader = reader
        self._references = references
        self._inputs = inputs or {}

    def execute(self, plan: AnalysisPlan) -> AnalysisResult:
        if plan.status != "approved":
            return self._not_executed(plan, "El plan debe estar aprobado antes de ejecutarse.")
        if plan.technique not in self._IMPLEMENTED_TECHNIQUES:
            return self._failed(
                plan,
                f"La técnica {plan.technique or 'vacía'} aún no está implementada por el motor.",
            )
        reference = self._references.get(plan.dataset_id)
        if reference is None:
            return self._failed(
                plan, "No existe una referencia autorizada para el dataset del plan."
            )
        try:
            table = self._reader.read(reference)
            descriptions = describe_table(table) if plan.technique == "descriptive_summary" else []
            calculation = (
                None
                if plan.technique == "descriptive_summary"
                else self._calculate(plan.technique, self._inputs.get(plan.id))
            )
        except (OSError, ValueError, OverflowError, StatisticalCalculationError) as error:
            return self._failed(plan, str(error))

        metrics = self._metrics(descriptions)
        warnings = list(table.warnings)
        assumptions = [
            AssumptionCheck(
                name="descriptive_input_validation",
                status="passed",
                details="El dataset fue validado por DatasetReader antes del cálculo.",
            )
        ]
        if calculation is not None:
            metrics.extend(
                Metric(name=name, value=value) for name, value in calculation.metrics.items()
            )
            warnings.extend(calculation.warnings)
            assumptions.extend(self._assumption_checks(plan.technique, self._inputs[plan.id]))
        return AnalysisResult(
            schema_version="1.0.0",
            id=f"result-{plan.id}",
            analysis_plan_id=plan.id,
            dataset_id=plan.dataset_id,
            status="completed",
            metrics=metrics,
            assumptions=assumptions,
            warnings=warnings,
            engine_version=self.VERSION,
            interpretation=(
                f"Se ejecutó {plan.technique} de forma determinista sobre el dataset autorizado."
            ),
        )

    @staticmethod
    def _calculate(technique: str | None, data: AnalysisInput | None) -> TechniqueResult:
        if data is None:
            raise StatisticalCalculationError(
                "La técnica requiere columnas seleccionadas mediante AnalysisInput."
            )
        if technique == "cronbach_alpha":
            return cronbach_alpha(data.matrix)
        if technique == "pearson":
            return pearson(data.left, data.right)
        if technique == "spearman":
            return spearman(data.left, data.right)
        if technique == "t_independent":
            return t_independent(data.left, data.right)
        if technique == "t_paired":
            return t_paired(data.left, data.right)
        if technique == "t_welch":
            return t_welch(data.left, data.right)
        if technique == "mann_whitney":
            return mann_whitney(data.left, data.right)
        if technique == "wilcoxon":
            return wilcoxon(data.left, data.right)
        if technique == "anova":
            return anova(data.groups)
        if technique == "anova_welch":
            return anova_welch(data.groups)
        if technique == "kruskal_wallis":
            return kruskal_wallis(data.groups)
        if technique == "tukey":
            return tukey(data.groups, data.labels or None)
        if technique == "games_howell":
            return games_howell(data.groups, data.labels or None)
        if technique == "chi_square":
            return chi_square(data.left, data.right)
        if technique == "fisher_exact":
            return fisher_exact(data.left, data.right)
        if technique == "ancova":
            return ancova(data.outcome, data.group, data.covariate)
        if technique == "linear_regression_simple":
            return linear_regression_simple(data.left, data.right)
        if technique == "linear_regression_multiple":
            return linear_regression_multiple(data.predictors, data.outcome)
        raise StatisticalCalculationError(f"Técnica no permitida: {technique}")

    @staticmethod
    def _assumption_checks(technique: str, data: AnalysisInput) -> list[AssumptionCheck]:
        independence_diagnostic = independence()
        checks = [
            AssumptionCheck(
                name=independence_diagnostic.name,
                status=independence_diagnostic.status,
                details=independence_diagnostic.details,
            )
        ]
        if (
            technique
            in {
                "t_independent",
                "t_welch",
                "mann_whitney",
                "anova",
                "anova_welch",
            }
            and data.groups
        ):
            diagnostic = homogeneity(data.groups)
            checks.append(
                AssumptionCheck(
                    name=diagnostic.name,
                    status=diagnostic.status,
                    details=diagnostic.details,
                )
            )
        if technique in {"t_independent", "t_welch", "anova", "anova_welch"}:
            labels = data.labels or tuple(
                f"group_{index}" for index in range(1, len(data.groups) + 1)
            )
            for label, group in zip(labels, data.groups, strict=True):
                diagnostic = normality(group, name=f"normality_{label}")
                checks.append(
                    AssumptionCheck(
                        name=diagnostic.name,
                        status=diagnostic.status,
                        details=diagnostic.details,
                    )
                )
        if technique in {"pearson", "spearman", "linear_regression_simple"}:
            diagnostic = normality(data.left)
            checks.append(
                AssumptionCheck(
                    name=diagnostic.name,
                    status=diagnostic.status,
                    details=diagnostic.details,
                )
            )
        if technique == "linear_regression_multiple":
            diagnostic = normality(data.outcome)
            checks.append(
                AssumptionCheck(
                    name=diagnostic.name,
                    status=diagnostic.status,
                    details=diagnostic.details,
                )
            )
        return checks

    @staticmethod
    def _metrics(descriptions: list[DescriptiveResult]) -> list[Metric]:
        metrics: list[Metric] = []
        for description in descriptions:
            prefix = description.column
            if description.numeric is not None:
                summary = description.numeric
                metrics.extend(
                    [
                        Metric(name=f"{prefix}.valid_count", value=summary.valid_count),
                        Metric(name=f"{prefix}.missing_count", value=summary.missing_count),
                    ]
                )
                for name, value in (
                    ("mean", summary.mean),
                    ("median", summary.median),
                    ("minimum", summary.minimum),
                    ("maximum", summary.maximum),
                    ("sample_standard_deviation", summary.sample_standard_deviation),
                    ("sample_variance", summary.sample_variance),
                ):
                    if value is not None:
                        metrics.append(Metric(name=f"{prefix}.{name}", value=value))
                if summary.quantiles:
                    metrics.extend(
                        Metric(name=f"{prefix}.{name}", value=value)
                        for name, value in summary.quantiles.items()
                    )
            elif description.categorical is not None:
                summary = description.categorical
                metrics.extend(
                    [
                        Metric(name=f"{prefix}.valid_count", value=summary.valid_count),
                        Metric(name=f"{prefix}.missing_count", value=summary.missing_count),
                    ]
                )
                for frequency in summary.frequencies:
                    metrics.extend(
                        [
                            Metric(
                                name=f"{prefix}.category.{frequency.value}.count",
                                value=frequency.count,
                            ),
                            Metric(
                                name=f"{prefix}.category.{frequency.value}.percentage",
                                value=frequency.percentage,
                            ),
                        ]
                    )
        return metrics

    @staticmethod
    def _not_executed(plan: AnalysisPlan, warning: str) -> AnalysisResult:
        return AnalysisResult(
            schema_version="1.0.0",
            id=f"result-{plan.id}",
            analysis_plan_id=plan.id,
            dataset_id=plan.dataset_id,
            status="not_executed",
            warnings=[warning],
            engine_version=DeterministicStatisticalEngine.VERSION,
        )

    @staticmethod
    def _failed(plan: AnalysisPlan, warning: str) -> AnalysisResult:
        return AnalysisResult(
            schema_version="1.0.0",
            id=f"result-{plan.id}",
            analysis_plan_id=plan.id,
            dataset_id=plan.dataset_id,
            status="failed",
            warnings=[warning],
            engine_version=DeterministicStatisticalEngine.VERSION,
        )
