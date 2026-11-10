"""Pure C4 checks on authorized rows. No final hypothesis tests or I/O."""

import math
import warnings
from collections import Counter

import numpy as np
import scipy
from scipy import stats

from app.shared.diagnostics_v2 import (
    AnalysisProfileV2,
    DiagnosticCheckV2,
    DiagnosticFigureV2,
    GroupCountV2,
)

VERSION = "diagnostics-1.0.0"
ENGINE = f"scipy-{scipy.__version__}"


def _missing(value, markers):
    return (
        value is None
        or not value.strip()
        or value.strip().casefold() in {m.strip().casefold() for m in markers}
    )


def _quantitative(variable):
    return bool(variable.measurement_scale.confirmation) and (
        variable.measurement_scale.value in {"interval", "ratio"}
        and variable.identifier_confirmed.value is not True
    )


def _confirmed(fact):
    return fact.confirmation is not None and fact.value not in (None, "", "unknown")


def _finite_result(result):
    return math.isfinite(float(result.statistic)) and math.isfinite(float(result.pvalue))


def evaluate(intent, dataset, dictionary, rows, requested):
    """Complete cases jointly over selected variables; numeric invalids separately counted.

    Wide differences always first measurement minus second, matching t_paired/wilcoxon.
    Graph reductions are explicit; every check uses all eligible rows.
    """
    by_id = {v.id: v for v in dictionary.variables}
    selected = [by_id[v] for v in intent.variable_ids]
    columns = {c.id: c for c in dataset.columns}
    variables = {v.column_ids[0]: v for v in selected if len(v.column_ids) == 1}
    notes = [
        "Compatible no demuestra normalidad ni independencia. Revisa cómo se obtuvieron los datos.",
        "Estos diagnósticos no eligen una técnica ni contrastan la pregunta final.",
    ]
    if not _confirmed(intent.observational_unit):
        notes.append(
            "¿Qué representa una observación en este análisis? Revísalo y confírmalo aquí."
        )
    if not _confirmed(intent.observations) and intent.kind != "descriptive":
        notes.append(
            "¿Se midieron entidades distintas o las mismas? El contexto general no lo decide."
        )
    if not _confirmed(intent.identification):
        notes.append("Explica cómo reconoces cada entidad y si puede aparecer en varias filas.")
    complete, missing_count, invalid_count = [], 0, 0
    for row in rows:
        if not variables or len(variables) != len(selected):
            missing_count += 1
            continue
        if any(_missing(row[columns[c].position], v.missing_markers) for c, v in variables.items()):
            missing_count += 1
            continue
        converted = {}
        invalid = False
        for c, v in variables.items():
            value = row[columns[c].position]
            if _quantitative(v):
                try:
                    value = float(value)
                    if not math.isfinite(value):
                        invalid = True
                except (ValueError, OverflowError):
                    invalid = True
            converted[c] = value
        if invalid:
            invalid_count += 1
        else:
            complete.append((row, converted))
    effective = [r for _, r in complete]
    profile = AnalysisProfileV2(
        total_rows=len(rows),
        complete_case_count=len(effective),
        excluded_count=len(rows) - len(effective),
        excluded_missing_count=missing_count,
        excluded_invalid_count=invalid_count,
    )
    checks, figures = [], []

    def record(name, target, n, details, method="recuento", status="compatible", result=None):
        checks.append(
            DiagnosticCheckV2(
                name=name,
                target=target,
                case_count=n,
                details=details,
                method=method,
                method_version=ENGINE if result else VERSION,
                status=status,
                statistic=float(result.statistic) if result else None,
                p_value=float(result.pvalue) if result else None,
            )
        )

    def skip(name, reason, target="análisis", n=0):
        record(name, target, n, reason, method="no calculado", status="not_checked")

    if "complete_cases" in requested:
        record(
            "complete_cases",
            "variables seleccionadas",
            len(effective),
            f"{len(rows)} filas; {len(effective)} completas; "
            f"{missing_count} excluidas por faltantes "
            f"y {invalid_count} por valores no numéricos/no finitos en variables cuantitativas.",
        )

    group = intent.group_column_id
    group_counts = Counter(r[group] for r in effective) if group in variables else Counter()
    profile.group_counts = [
        GroupCountV2(label=str(label), count=count) for label, count in group_counts.items()
    ]
    if "group_sizes" in requested:
        if group in variables:
            record(
                "group_sizes",
                "grupos en casos completos",
                len(effective),
                f"{len(group_counts)} grupos observados; no demuestra independencia.",
            )
        else:
            skip(
                "group_sizes", "No se seleccionó una variable de grupo; no se deduce por su nombre."
            )

    paired = intent.paired_columns
    paired_ready = bool(
        paired
        and intent.observations.value == "paired"
        and _confirmed(intent.observations)
        and intent.linkage.value == "same_row"
        and _confirmed(intent.linkage)
        and _confirmed(intent.observational_unit)
        and _confirmed(intent.identification)
        and _confirmed(intent.comparison_notes)
    )
    pairing_reason = (
        "Revisa las dos mediciones, qué entidad se repite, cómo se identifica y si cada fila "
        "corresponde realmente a esa misma entidad. Nombres o una unión por ID no lo demuestran."
    )
    if intent.linkage.value == "unavailable":
        pairing_reason = (
            "No es posible establecer pares según esta intención. "
            "No se emparejan filas por posición."
        )
        paired_ready = False
    if paired_ready and intent.identifier_column_id:
        id_column = columns[intent.identifier_column_id]
        ids = [row[id_column.position] for row, _ in complete]
        id_variable = next((v for v in dictionary.variables if id_column.id in v.column_ids), None)
        markers = id_variable.missing_markers if id_variable else []
        if any(_missing(v, markers) for v in ids) or len(set(ids)) != len(ids):
            paired_ready = False
            pairing_reason = (
                "Hay identificadores vacíos o repetidos entre casos completos; "
                "aclara la unidad y las repeticiones."
            )
    if paired_ready:
        profile.complete_pair_count = len(effective)
    if "paired_cases" in requested:
        if paired_ready:
            record(
                "paired_cases",
                "pares por fila revisados",
                len(effective),
                f"{len(effective)} pares completos; {profile.excluded_count} filas excluidas. "
                "Correspondencia declarada por el usuario, no demostrada por la prueba.",
            )
        else:
            skip("paired_cases", pairing_reason)

    numeric_columns = [c for c, v in variables.items() if _quantitative(v) and c != group]
    targets = []
    if intent.kind == "comparison" and intent.observations.value == "paired":
        if paired_ready and all(
            c in numeric_columns
            for c in (
                paired.before_column_id,
                paired.after_column_id,
            )
        ):
            differences = [
                r[paired.before_column_id] - r[paired.after_column_id] for r in effective
            ]
            profile.zero_difference_count = sum(d == 0 for d in differences)
            targets = [("Diferencias: primera − segunda medición", differences)]
        else:
            notes.append(
                pairing_reason + " Las diferencias necesitan escalas cuantitativas revisadas."
            )
    elif intent.kind == "comparison" and group in variables:
        targets = [
            (
                f"{variables[c].name.value or columns[c].name} · grupo {label}",
                [r[c] for r in effective if r[group] == label],
            )
            for c in numeric_columns
            for label in group_counts
        ]
    else:
        targets = [
            (variables[c].name.value or columns[c].name, [r[c] for r in effective])
            for c in numeric_columns
        ]

    for check in ("distribution", "normality", "influence"):
        if check not in requested:
            continue
        if not targets:
            skip(
                check,
                "Faltan variables cuantitativas con escala confirmada o pares revisados. "
                "Los códigos numéricos no bastan; revisa el diccionario en Datos.",
            )
        for target, values in targets:
            n = len(values)
            if not n or not all(math.isfinite(v) for v in values):
                skip(check, "Sin casos completos finitos para este alcance.", target, n)
                continue
            constant = min(values) == max(values)
            if check == "normality":
                if constant or not 3 <= n <= 5000:
                    skip(
                        check,
                        "Shapiro–Wilk requiere 3–5000 casos y variación; "
                        "fuera del rango se conserva la evaluación gráfica, sin muestreo oculto.",
                        target,
                        n,
                    )
                    continue
                with warnings.catch_warnings(), np.errstate(all="ignore"):
                    warnings.simplefilter("ignore")
                    result = stats.shapiro(values, nan_policy="raise")
                if _finite_result(result):
                    record(
                        check,
                        target,
                        n,
                        "Evaluación bilateral de distribución, no de la pregunta final. "
                        "Compatible no prueba normalidad y no determina por sí solo la técnica.",
                        method="Shapiro–Wilk",
                        result=result,
                        status="incompatible" if result.pvalue < intent.alpha else "compatible",
                    )
                else:
                    skip(
                        check, "La precisión numérica no permite calcular Shapiro–Wilk.", target, n
                    )
            elif check == "distribution":
                try:
                    with np.errstate(all="raise"):
                        counts, edges = np.histogram(
                            values, bins=min(20, max(1, math.ceil(math.sqrt(n))))
                        )
                        x = edges[:-1] / 2 + edges[1:] / 2
                        theoretical, ordered = stats.probplot(values, dist="norm", fit=False)
                    indices = np.unique(np.linspace(0, n - 1, min(n, 200), dtype=int))
                    all_values = [*x, *theoretical[indices], *ordered[indices]]
                    if not all(math.isfinite(float(v)) for v in all_values):
                        raise ValueError("nonfinite")
                    figures.extend(
                        [
                            DiagnosticFigureV2(
                                kind="histogram",
                                target=target,
                                x_label="Valor",
                                y_label="Frecuencia",
                                x=x.tolist(),
                                y=counts.astype(float).tolist(),
                                details=f"Todas las {n} observaciones; "
                                f"{len(counts)} intervalos de igual ancho.",
                            ),
                            DiagnosticFigureV2(
                                kind="qq",
                                target=target,
                                x_label="Cuantil normal teórico",
                                y_label="Valor observado",
                                x=theoretical[indices].tolist(),
                                y=ordered[indices].tolist(),
                                details=f"Posiciones Filliben; {len(indices)} puntos de "
                                f"{n} ordenados para visualizar; "
                                "los cálculos usan todos los casos. Revisa curvaturas y extremos.",
                            ),
                        ]
                    )
                    record(
                        check,
                        target,
                        n,
                        "Histograma y Q–Q normal; no certifican independencia.",
                        method="histograma / Q–Q Filliben",
                    )
                except (ValueError, OverflowError, FloatingPointError):
                    skip(
                        check,
                        "Rango numérico fuera de la precisión disponible para graficar.",
                        target,
                        n,
                    )
            else:
                if n < 4:
                    skip(
                        check,
                        "Se requieren al menos 4 casos para explorar extremos con IQR.",
                        target,
                        n,
                    )
                    continue
                with np.errstate(all="ignore"):
                    q1, q3 = np.quantile(values, [0.25, 0.75], method="linear")
                    low, high = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
                if not all(math.isfinite(v) for v in (low, high)):
                    skip(check, "Rango numérico fuera de precisión para IQR.", target, n)
                    continue
                count = sum(v < low or v > high for v in values)
                record(
                    check,
                    target,
                    n,
                    f"{count} observaciones fuera de cercas 1.5 IQR (cuantiles tipo 7). "
                    "Son señales exploratorias: no borrar casos automáticamente "
                    "ni concluir influencia, "
                    "linealidad o monotonía.",
                    method="cercas 1.5 IQR",
                    status="incompatible" if count else "compatible",
                )

    if "influence" in requested and intent.kind == "association" and len(numeric_columns) == 2:
        # Scatter is visual evidence only; never emit an unrequested final correlation.
        indices = np.unique(np.linspace(0, len(effective) - 1, min(len(effective), 500), dtype=int))
        if len(indices):
            left, right = numeric_columns
            figures.append(
                DiagnosticFigureV2(
                    kind="scatter",
                    target="Asociación: revisar dispersión",
                    x_label=variables[left].name.value or columns[left].name,
                    y_label=variables[right].name.value or columns[right].name,
                    x=[effective[i][left] for i in indices],
                    y=[effective[i][right] for i in indices],
                    details=f"{len(indices)} de {len(effective)} casos espaciados "
                    "por índice para visualizar. No es prueba de linealidad ni monotonía; "
                    "revisa también los extremos por variable.",
                )
            )

    if "homogeneity" in requested:
        eligible = (
            intent.kind == "comparison"
            and intent.observations.value == "independent"
            and _confirmed(intent.observations)
            and _confirmed(intent.observational_unit)
            and _confirmed(intent.identification)
            and _confirmed(intent.comparison_notes)
            and len(numeric_columns) == 1
            and len(group_counts) == 2
        )
        samples = (
            [
                [r[numeric_columns[0]] for r in effective if r[group] == label]
                for label in group_counts
            ]
            if eligible
            else []
        )
        if not samples or any(len(s) < 2 for s in samples):
            skip(
                "homogeneity",
                "Requiere dos grupos revisados como independientes, una medida "
                "cuantitativa y al menos dos casos completos por grupo. "
                "No aplica a diferencias pareadas.",
            )
        else:
            with warnings.catch_warnings(), np.errstate(all="ignore"):
                warnings.simplefilter("ignore")
                result = stats.levene(*samples, center="median", nan_policy="raise")
            if _finite_result(result):
                record(
                    "homogeneity",
                    "dos grupos independientes revisados",
                    len(effective),
                    "Levene centrado en mediana (Brown–Forsythe), aproximación F. "
                    "No acredita igualdad de varianzas ni selecciona "
                    "Student/Welch automáticamente.",
                    method="Brown–Forsythe",
                    result=result,
                    status="incompatible" if result.pvalue < intent.alpha else "compatible",
                )
            else:
                skip(
                    "homogeneity",
                    "Sin variación suficiente en desviaciones absolutas o precisión numérica.",
                    n=len(effective),
                )
    profile.warnings = notes.copy()
    return profile, checks, figures, notes
