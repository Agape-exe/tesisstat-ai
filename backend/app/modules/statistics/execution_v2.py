"""Adapt authorized v2 cases to the S04A pure functions, without v1 artifacts."""

from collections import Counter
from dataclasses import dataclass

from app.modules.statistics import comparisons, inferential, nonparametric
from app.modules.statistics.descriptive import describe_numeric
from app.modules.statistics.diagnostics import _quantitative, evaluate, select_cases
from app.modules.statistics.planning_v2 import case_counts
from app.shared.plans_v2 import ResultColumn, ResultMetric, ResultTable

LABELS = {
    "mean": "Media",
    "median": "Mediana",
    "minimum": "Mínimo",
    "maximum": "Máximo",
    "sample_standard_deviation": "Desviación estándar muestral",
    "sample_variance": "Varianza muestral",
    "p_value": "p bilateral",
    "r": "Correlación r",
    "rho": "Correlación de rangos",
    "t_statistic": "Estadístico t",
    "degrees_of_freedom": "Grados de libertad",
    "mean_difference": "Diferencia de medias (primera − segunda)",
    "n": "Casos del contraste",
    "n_left": "Casos del primer grupo",
    "n_right": "Casos del segundo grupo",
    "cohens_d": "d de Cohen",
    "cohens_dz": "d de Cohen pareada",
    "w": "W mínimo",
    "w_positive": "Suma de rangos positivos",
    "w_negative": "Suma de rangos negativos",
    "u": "U mínimo",
    "z_statistic": "Estadístico z",
    "rank_effect": "Magnitud z/raíz(n)",
    "rank_biserial_effect": "Magnitud del efecto de rangos (sin dirección)",
    "mean_difference_ci_95_low": "Límite inferior: diferencia de medias",
    "mean_difference_ci_95_high": "Límite superior: diferencia de medias",
}

FUNCTIONS = {
    "pearson": inferential.pearson,
    "spearman": inferential.spearman,
    "t_welch": comparisons.t_welch,
    "t_independent": comparisons.t_independent,
    "t_paired": comparisons.t_paired,
    "mann_whitney": nonparametric.mann_whitney,
    "wilcoxon": nonparametric.wilcoxon,
}


@dataclass
class ExecutionInputV2:
    snapshot: object
    dataset: object
    dictionary: object
    rows: list
    technique: str


def execute(data: ExecutionInputV2):
    i, ds, dictionary = data.snapshot.intent, data.dataset, data.dictionary
    selected = [next(v for v in dictionary.variables if v.id == id_) for id_ in i.variable_ids]
    complete, _, _ = select_cases(i, ds, dictionary, data.rows)
    effective = [r for _, r in complete]
    profile, _, _, _ = evaluate(i, ds, dictionary, data.rows, ["complete_cases"])
    counts = case_counts(profile, data.technique)
    metrics, tables, warnings = [], [], []
    if data.technique == "cronbach_alpha":
        from app.modules.statistics.instrument_v2 import ReliabilityNotCalculable, alpha_conditions

        matrix = [[r[v.column_ids[0]] for v in selected] for r in effective]
        reason = alpha_conditions(matrix, item_count=len(selected))
        if reason:
            raise ReliabilityNotCalculable(reason)
        try:
            result = inferential.cronbach_alpha(matrix)
        except (inferential.StatisticalCalculationError, ArithmeticError) as exc:
            raise ReliabilityNotCalculable(str(exc)) from exc
        return (
            counts,
            [
                ResultMetric(
                    key=k,
                    label={
                        "alpha": "Alfa de Cronbach",
                        "n": "Casos completos",
                        "items": "Ítems",
                    }.get(k, k),
                    value=value,
                )
                for k, value in result.metrics.items()
            ],
            [],
            list(result.warnings),
        )
    if data.technique == "descriptive_summary":
        for v in selected:
            values = [r[v.column_ids[0]] for r in effective]
            label = v.name.value or v.id
            if _quantitative(v):
                summary = describe_numeric([str(value) for value in values])
                warnings.extend(summary.warnings)
                for name in (
                    "mean",
                    "median",
                    "minimum",
                    "maximum",
                    "sample_standard_deviation",
                    "sample_variance",
                ):
                    value = getattr(summary, name)
                    metrics.append(
                        ResultMetric(
                            key=f"{v.id}.{name}",
                            label=f"{label} · {LABELS.get(name, name)}",
                            value=value,
                            reason="Sin casos o variación/tamaño suficientes."
                            if value is None
                            else None,
                        )
                    )
                for name, value in (summary.quantiles or {}).items():
                    metrics.append(
                        ResultMetric(
                            key=f"{v.id}.{name}",
                            label=f"{label} · {LABELS.get(name, name)}",
                            value=value,
                        )
                    )
                warnings.append(
                    f"{label}: moda(s) {', '.join(map(str, summary.modes)) or 'no definida'}; "
                    "cuantiles tipo 7; varianza muestral n−1."
                )
            else:
                frequencies = Counter(str(value) for value in values)
                ordered = (
                    sorted(frequencies, key=lambda x: v.category_order.index(x))
                    if v.category_order
                    else sorted(frequencies)
                )
                tables.append(
                    ResultTable(
                        id=v.id,
                        title=f"{label}: frecuencias sobre {len(values)} casos completos",
                        columns=[
                            ResultColumn(key="category", label="Categoría", type="string"),
                            ResultColumn(key="count", label="Frecuencia", type="number"),
                            ResultColumn(
                                key="percentage", label="Porcentaje de casos usados", type="number"
                            ),
                        ],
                        rows=[
                            {
                                "category": key,
                                "count": frequencies[key],
                                "percentage": 100 * frequencies[key] / len(values),
                            }
                            for key in ordered
                        ],
                    )
                )
        return counts, metrics, tables, warnings

    def values(v):
        raw = [r[v.column_ids[0]] for r in effective]
        if v.measurement_scale.value == "ordinal":
            # Explicit human order; no numeric-code or alphabetical inference.
            return [float(v.category_order.index(str(value)) + 1) for value in raw]
        return raw

    if data.technique in {"t_welch", "t_independent", "mann_whitney"}:
        outcome = next(v for v in selected if i.group_column_id not in v.column_ids)
        vector = values(outcome)
        labels = [g.label for g in counts.groups]
        left, right = [
            [
                value
                for row, value in zip(effective, vector, strict=True)
                if str(row[i.group_column_id]) == label
            ]
            for label in labels
        ]
        warnings.append(f"Orden de grupos: {labels[0]} − {labels[1]} (orden de aparición).")
    elif data.technique in {"t_paired", "wilcoxon"}:
        left = [r[i.paired_columns.before_column_id] for r in effective]
        right = [r[i.paired_columns.after_column_id] for r in effective]
    else:
        left, right = [values(v) for v in selected]
    result = FUNCTIONS[data.technique](left, right)
    # Check that the pure adapter has not silently changed the diagnosed case set.
    if "n_left" in result.metrics and (
        result.metrics["n_left"] != len(left) or result.metrics["n_right"] != len(right)
    ):
        raise inferential.StatisticalCalculationError(
            "Los recuentos del motor no coinciden con los diagnósticos."
        )
    if "n" in result.metrics and result.metrics["n"] != counts.used:
        raise inferential.StatisticalCalculationError(
            "El motor excluyó casos adicionales; resultado no publicable."
        )
    if data.technique == "wilcoxon":
        nonzero = sum(a != b for a, b in zip(left, right, strict=True))
        warnings.append(
            f"{counts.pairs} pares completos; {counts.pairs - nonzero} diferencias cero "
            f"descartadas del contraste; {nonzero} diferencias no nulas."
        )
    if data.technique == "wilcoxon":
        diffs = [a - b for a, b in zip(left, right, strict=True)]
        magnitudes = [abs(d) for d in diffs if d != 0]
        exact = (
            len(magnitudes) <= 20
            and len(magnitudes) == len(diffs)
            and len(set(magnitudes)) == len(magnitudes)
        )
        warnings.append(
            "Método aplicado: exacto por signos."
            if exact
            else "Método aplicado: aproximación normal, ceros wilcox, "
            "corrección de empates y continuidad 0.5."
        )
    elif data.technique == "mann_whitney":
        exact = len(left) + len(right) <= 20 and len(set(left + right)) == len(left) + len(right)
        warnings.append(
            "Método aplicado: exacto por asignaciones."
            if exact
            else "Método aplicado: aproximación normal con empates y continuidad 0.5."
        )
    for key, value in result.metrics.items():
        label = LABELS.get(key, key.replace("_", " "))
        if "ci_95" in key:
            label += " (IC del 95 %)"
        metrics.append(ResultMetric(key=key, label=label, value=value))
    return counts, metrics, tables, [*warnings, *result.warnings]
