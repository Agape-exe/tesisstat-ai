"""One deterministic format policy for browser, tutor metric citations and reports."""

from app.shared.reports_v2 import DisplayMetricV2, DisplayTableV2, ResultPresentationV2

TECHNIQUES = {
    "descriptive_summary": "Resumen descriptivo",
    "pearson": "Correlación de Pearson",
    "spearman": "Correlación de Spearman",
    "t_welch": "t de Welch",
    "t_independent": "t de Student con varianza agrupada",
    "mann_whitney": "Mann–Whitney",
    "t_paired": "t pareada",
    "wilcoxon": "Wilcoxon",
    "cronbach_alpha": "Alfa de Cronbach",
}
METRIC_LABELS = {
    "p0": "Percentil 0 (mínimo)",
    "p100": "Percentil 100 (máximo)",
    "p25": "Percentil 25",
    "p50": "Percentil 50 (mediana)",
    "p75": "Percentil 75",
    "r_ci_95_low": "Límite inferior de r (IC del 95 %)",
    "r_ci_95_high": "Límite superior de r (IC del 95 %)",
    "rho_ci_95_low": "Límite inferior de rho (IC del 95 %, aproximado)",
    "rho_ci_95_high": "Límite superior de rho (IC del 95 %, aproximado)",
}
CHECKS = {
    "complete_cases": "Casos completos",
    "group_sizes": "Tamaños de grupos",
    "paired_cases": "Pares completos",
    "distribution": "Distribución",
    "normality": "Normalidad",
    "homogeneity": "Homogeneidad",
    "influence": "Extremos e influencia",
}
CHECK_STATES = {
    "compatible": "Compatible dentro del límite",
    "incompatible": "Señal para revisar",
    "not_checked": "No evaluado",
}


def metric_label(metric):
    key = metric.key.rsplit(".", 1)[-1]
    if key not in METRIC_LABELS:
        return metric.label
    prefix = metric.label.split(" · ")[0] + " · " if " · " in metric.label else ""
    return prefix + METRIC_LABELS[key]


def metric_unit(metric):
    if metric.unit:
        return metric.unit
    key = metric.key.rsplit(".", 1)[-1]
    if key in {"n", "n_left", "n_right"}:
        return "casos"
    if key in {
        "r",
        "rho",
        "p_value",
        "alpha",
        "cohens_d",
        "cohens_dz",
        "rank_effect",
        "rank_biserial_effect",
    } or key.startswith(("r_ci_", "rho_ci_")):
        return "sin unidad"
    if key in {
        "mean",
        "median",
        "minimum",
        "maximum",
        "sample_standard_deviation",
        "p25",
        "p50",
        "p75",
        "mean_difference",
    } or key.startswith("mean_difference_ci_"):
        return "unidad de la variable no declarada"
    if key == "sample_variance":
        return "cuadrado de la unidad no declarada"
    return None


def format_number(value, key=""):
    if value is None:
        return "No calculable"
    if key.endswith("p_value"):
        if value == 0:
            return "< límite de precisión numérica (no es probabilidad nula)"
        if value < 0.001:
            return "< 0,001"
    return format(value, ".6g").replace(".", ",")


def descriptive_tables(result):
    if result.technique != "descriptive_summary":
        return []
    groups = {}
    for metric in result.metrics:
        variable, _, suffix = metric.key.rpartition(".")
        row = groups.setdefault(variable, {"name": metric.label.split(" · ")[0]})
        row[suffix] = format_number(metric.value)
        if metric.unit:
            row["unit"] = metric.unit
    tables = []
    for index, (title, keys, labels) in enumerate(
        (
            (
                "Métricas descriptivas principales",
                ["mean", "median", "sample_standard_deviation", "minimum", "maximum"],
                ["Media", "Mediana", "DE", "Mínimo", "Máximo"],
            ),
            (
                "Métricas descriptivas complementarias",
                ["sample_variance", "p25", "p50", "p75"],
                ["Varianza", "P25", "P50", "P75"],
            ),
        )
    ):
        if groups:
            tables.append(
                DisplayTableV2(
                    id=f"{result.id}-descriptive-{index}",
                    title=title,
                    columns=["Variable", *labels],
                    rows=[
                        [
                            row["name"] + (" (" + row["unit"] + ")" if "unit" in row else ""),
                            *[row.get(k, "No calculable") for k in keys],
                        ]
                        for row in groups.values()
                    ],
                )
            )
    return tables


def present(result):
    text = None
    if result.status == "completed":
        text = (
            f"Se utilizaron {result.case_counts.used} de {result.case_counts.total} casos "
            f"mediante {TECHNIQUES[result.technique]}. "
        )
        if result.technique != "descriptive_summary":
            for metric in result.metrics:
                if metric.key in {"r", "rho", "alpha", "mean_difference", "p_value"}:
                    text += f"{metric_label(metric)}: {format_number(metric.value, metric.key)}. "
        if result.technique == "cronbach_alpha":
            text += "El coeficiente no demuestra validez ni unidimensionalidad. "
        if result.technique == "descriptive_summary":
            summaries = {}
            for metric in result.metrics:
                variable, _, suffix = metric.key.rpartition(".")
                if suffix in {"mean", "median", "minimum", "maximum", "sample_standard_deviation"}:
                    summaries.setdefault(variable, []).append(metric)
            for metrics in summaries.values():
                name = metrics[0].label.split(" · ")[0]
                text += (
                    name
                    + ": "
                    + "; ".join(
                        f"{m.label.split(' · ')[-1].lower()} {format_number(m.value)}"
                        + (f" {m.unit}" if m.unit else "")
                        for m in metrics
                        if m.value is not None
                    )
                    + ". "
                )
            for table in result.tables:
                if table.rows and "count" in table.rows[0]:
                    text += f"{table.title}: {len(table.rows)} categorías observadas. "
            text += (
                " Los resúmenes describen los casos completos conjuntos "
                "de las variables seleccionadas; "
            )
            text += "no prueban hipótesis ni representan necesariamente a toda la población."
            text += (
                " La media resume el nivel promedio; la mediana es el valor central y DE "
                "es la desviación estándar muestral, que indica dispersión. "
                if summaries
                else " Las frecuencias cuentan las observaciones por categoría; los porcentajes "
                "usan como denominador los casos utilizados. "
            )
            text += (
                "Esto responde a una pregunta descriptiva; no establece diferencias entre "
                "grupos ni relaciones entre variables. Como siguiente paso puedes explorar "
                "una relación o comparación, revisando antes qué representan las observaciones."
            )
            if summaries and not any(m.unit for m in result.metrics):
                text += " Las unidades de las medidas no se han declarado."
        elif result.technique in {"pearson", "spearman"}:
            text += (
                " El signo indica el sentido de la asociación; su magnitud no demuestra causalidad."
            )
        elif result.technique in {"t_paired", "wilcoxon"}:
            text += " El sentido de la diferencia es primera medición menos segunda."
        elif result.technique in {"t_welch", "t_independent", "mann_whitney"}:
            text += " Revisa el orden de los grupos guardado en advertencias."
        if result.technique in {"mann_whitney", "wilcoxon"}:
            text += " El contraste de rangos no equivale por sí solo a una diferencia de medianas."
        if any(m.key == "p_value" for m in result.metrics):
            text += " La significación estadística no determina relevancia práctica."
        if any("_ci_95_" in m.key for m in result.metrics):
            text += " Los intervalos disponibles son IC del 95 %; revisa sus aproximaciones."
    return ResultPresentationV2(
        result_id=result.id,
        status_label={
            "completed": "Completado",
            "failed": "Fallido: error técnico del cálculo",
            "not_executed": "No ejecutado: no calculable con estas condiciones",
        }[result.status],
        technique_label=TECHNIQUES[result.technique],
        metrics=[
            DisplayMetricV2(
                key=m.key,
                label=metric_label(m),
                formatted=format_number(m.value, m.key),
                unit=metric_unit(m),
                reason=m.reason,
            )
            for m in result.metrics
        ],
        tables=descriptive_tables(result)
        + [
            DisplayTableV2(
                id=t.id,
                title=t.title,
                columns=[c.label for c in t.columns],
                rows=[
                    [
                        format_number(row[c.key], c.key)
                        if isinstance(row.get(c.key), (float, int))
                        else str(row.get(c.key) if row.get(c.key) is not None else "No disponible")
                        for c in t.columns
                    ]
                    for row in t.rows
                ],
            )
            for t in result.tables
        ],
        interpretation=text.strip() if text else None,
        interpretation_metric_keys=[m.key for m in result.metrics],
        interpretation_label="Explicación determinista basada en cifras guardadas · sin IA",
        limitations=list(
            dict.fromkeys(
                text
                if any("_ci_95_" in m.key for m in result.metrics)
                else text.replace(" Los intervalos disponibles son del 95 %.", "")
                for text in result.limitations
            )
        ),
        assumptions=[
            f"{CHECKS[c.name]} / {c.target}: "
            f"{CHECK_STATES[c.status]}. "
            f"{c.method}. Casos: {c.case_count}. "
            + (f"Estadístico: {format_number(c.statistic)}. " if c.statistic is not None else "")
            + (f"p: {format_number(c.p_value, 'p_value')}. " if c.p_value is not None else "")
            + f"{c.details}"
            for c in result.assumptions
        ],
    )
