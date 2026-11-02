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

from .descriptive import DescriptiveResult
from .ports import DatasetReader
from .service import describe_table


class DeterministicStatisticalEngine:
    """Execute only techniques explicitly implemented by this engine version."""

    VERSION = "statistics-engine-v1"
    _IMPLEMENTED_TECHNIQUES = frozenset({"descriptive_summary"})

    def __init__(
        self,
        reader: DatasetReader,
        references: Mapping[str, DatasetReference],
    ) -> None:
        self._reader = reader
        self._references = references

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
            descriptions = describe_table(table)
        except (OSError, ValueError) as error:
            return self._failed(plan, str(error))
        return AnalysisResult(
            schema_version="1.0.0",
            id=f"result-{plan.id}",
            analysis_plan_id=plan.id,
            dataset_id=plan.dataset_id,
            status="completed",
            metrics=self._metrics(descriptions),
            assumptions=[
                AssumptionCheck(
                    name="descriptive_input_validation",
                    status="passed",
                    details="El dataset fue validado por DatasetReader antes del cálculo.",
                )
            ],
            warnings=list(table.warnings),
            engine_version=self.VERSION,
            interpretation=(
                "Se ejecutó un resumen descriptivo determinista sobre el dataset autorizado."
            ),
        )

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
