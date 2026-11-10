"""Reusable deterministic selector; no Research I/O, provider or v1 package."""

from dataclasses import dataclass

from app.modules.statistics.diagnostics import _confirmed, _quantitative, evaluate, select_cases
from app.modules.statistics.numerical_policy import (
    NUMERICAL_POLICY_VERSION,
    POLICIES,
    VALIDATED_TECHNIQUES,
)
from app.shared.plans_v2 import CaseCounts, PlanQuestion

VERSION = "priority-selection-v2.1.0"
ENGINE = "statistics-engine-v2.0.0"
METHOD_VERSION = "priority-methods-1.0.0"
VERSIONS = {
    "selection": VERSION,
    "numerical": NUMERICAL_POLICY_VERSION,
    "engine": ENGINE,
    "methods": METHOD_VERSION,
}
METHODS = {name: f"{name}-two-sided-v2" for name in VALIDATED_TECHNIQUES}
METHODS["descriptive_summary"] = "descriptive-v2"


@dataclass
class PlanningInputV2:
    intent: object
    dataset: object
    dictionary: object
    rows: list
    diagnostics: list
    context: object = None


@dataclass
class Selection:
    technique: str | None
    questions: list
    rationale: str
    limitations: list
    counts: CaseCounts


def case_counts(profile, technique=None):
    zeros = (profile.zero_difference_count or 0) if technique == "wilcoxon" else 0
    return CaseCounts(
        total=profile.total_rows,
        used=profile.complete_case_count - zeros,
        excluded=profile.excluded_count + zeros,
        groups=profile.group_counts,
        pairs=profile.complete_pair_count,
    )


def select(data: PlanningInputV2):
    i, ds, dictionary, rows = data.intent, data.dataset, data.dictionary, data.rows
    profile, _, _, _ = evaluate(i, ds, dictionary, rows, ["complete_cases"])
    selected = [next(v for v in dictionary.variables if v.id == id_) for id_ in i.variable_ids]
    questions = []
    limits = [
        "Los casos completos se seleccionan conjuntamente entre todas las variables elegidas.",
        "El análisis no demuestra causalidad. Los intervalos disponibles son del 95 %.",
    ]
    technique = None

    def ask(field, question, destination="analysis"):
        if not any(q.field == field for q in questions):
            questions.append(
                PlanQuestion(
                    code=field.replace("/", "_"),
                    field=field,
                    question=question,
                    destination=destination,
                )
            )

    def fact(name, question):
        if not _confirmed(getattr(i, name)):
            ask(name, question)

    def condition(name, question):
        f = getattr(i.conditions, name)
        if not _confirmed(f) or f.value != "yes":
            ask("conditions/" + name, question)

    if data.context:
        if i.objective_id:
            objective = next(o for o in data.context.specific_objectives if o.id == i.objective_id)
            if not _confirmed(objective.text):
                ask(
                    "objective_id",
                    "Revisa y confirma el objetivo vinculado en Contexto.",
                    "context",
                )
        if i.hypothesis_id:
            hypothesis = next(h for h in data.context.hypotheses if h.id == i.hypothesis_id)
            if not _confirmed(hypothesis.statement):
                ask(
                    "hypothesis_id",
                    "Revisa y confirma la hipótesis vinculada en Contexto.",
                    "context",
                )
            if hypothesis.alternative in {"greater", "less"}:
                limits.append(
                    "La hipótesis vinculada conserva una dirección. Solo la intención "
                    "bilateral revisada puede ejecutarse; no se valida un contraste "
                    "unilateral."
                )
    if not i.confirmation:
        ask("confirmation", "Revisa y confirma esta intención antes de aprobar una propuesta.")
    if not selected:
        ask("variable_ids", "Selecciona las variables de este análisis.")
    for v in selected:
        if not _confirmed(v.measurement_scale) or v.measurement_scale.value == "unknown":
            ask(
                "scale/" + v.id,
                f"Revisa y confirma la escala de {v.name.value} en Datos.",
                "datasets",
            )
        if v.measurement_scale.value == "ordinal" and not v.category_order:
            ask("order/" + v.id, f"Confirma el orden de categorías de {v.name.value}.", "datasets")
        if len(v.column_ids) != 1:
            ask("column/" + v.id, "Cada variable debe enlazar una columna distinta.", "datasets")
    if len({c for v in selected for c in v.column_ids}) != len(selected):
        ask("variable_ids", "Selecciona variables vinculadas a columnas distintas.")
    if i.requested_technique and i.requested_technique not in VALIDATED_TECHNIQUES:
        ask(
            "requested_technique",
            "La técnica solicitada está fuera del alcance validado; revisa la intención.",
        )
    if i.kind == "descriptive":
        if i.estimand == "summary":
            technique = "descriptive_summary"
        else:
            ask("estimand", "Para describir datos selecciona un resumen descriptivo.")
    else:
        fact("question", "Explica qué pregunta concreta quieres responder.")
        fact("observational_unit", "¿Qué entidad representa cada observación de este análisis?")
        fact(
            "identification",
            "¿Cómo identificas las entidades y descartas repeticiones o agrupaciones?",
        )
        fact("observations", "Revisa la independencia o correspondencia de estas observaciones.")
        if i.observations.value not in {"independent", "paired"}:
            ask(
                "observations",
                "Diseños agrupados o repeticiones complejas no están validados; no pueden "
                "tratarse como independientes.",
            )
        if i.alternative != "two-sided":
            ask(
                "alternative",
                "Solo se validaron pruebas bilaterales. Revisa explícitamente la intención; "
                "no se cambia su dirección automáticamente.",
            )
        condition(
            "sampling_limit_accepted",
            "Revisa y acepta el límite de generalización: la selección de la muestra no queda "
            "acreditada por estos cálculos.",
        )
        limits.append(
            "La generalización está limitada por el muestreo; la aprobación acepta este "
            "límite visible."
        )
        if not data.diagnostics:
            ask(
                "diagnostics",
                "Solicita diagnósticos vigentes de esta intención antes de proponer inferencia.",
            )
    if i.kind != "descriptive" and any(v.identifier_confirmed.value is True for v in selected):
        ask(
            "variable_ids",
            "Los identificadores no son medidas para inferencia; revisa la selección.",
        )
    if i.observations.value == "paired" and i.group_column_id:
        ask(
            "group_column_id",
            "Esta comparación pareada no admite además una columna de agrupación.",
        )
    if i.observations.value == "independent" and i.paired_columns:
        ask(
            "paired_columns",
            "Revisa la intención: tiene columnas pareadas y observaciones independientes.",
        )
    if i.kind == "association" and (i.group_column_id or i.paired_columns):
        ask(
            "variable_ids",
            "La asociación validada usa dos variables sin agrupación ni pares adicionales.",
        )
    if i.kind == "association":
        if len(selected) != 2 or i.observations.value != "independent":
            ask(
                "variable_ids",
                "La asociación validada requiere dos variables y entidades independientes "
                "revisadas.",
            )
        elif i.estimand == "linear_association":
            if all(_quantitative(v) for v in selected):
                technique = "pearson"
                condition(
                    "linearity",
                    "Revisa la dispersión y confirma una relación aproximadamente lineal.",
                )
            else:
                ask(
                    "estimand",
                    "Pearson requiere dos medidas cuantitativas; revisa escalas y pregunta "
                    "sin sustituirla por rangos.",
                )
        elif i.estimand == "monotonic_association":
            if all(_quantitative(v) or v.measurement_scale.value == "ordinal" for v in selected):
                technique = "spearman"
                condition(
                    "monotonicity",
                    "Confirma que una relación monótona responde a la pregunta y es "
                    "pertinente para estos datos.",
                )
            else:
                ask(
                    "estimand",
                    "Spearman requiere medidas cuantitativas u ordinales con orden "
                    "confirmado, no nominales.",
                )
        else:
            ask("estimand", "Aclara si buscas asociación lineal o monótona.")
        if profile.complete_case_count < 3:
            ask("cases", "La asociación requiere al menos tres casos completos.", "datasets")
    elif i.kind == "comparison":
        fact(
            "comparison_notes",
            "Describe grupos, orden de mediciones y límites de esta comparación.",
        )
        if i.observations.value == "independent":
            outcomes = [v for v in selected if i.group_column_id not in v.column_ids]
            group = next((v for v in selected if i.group_column_id in v.column_ids), None)
            if len(selected) != 2 or len(outcomes) != 1 or not group:
                ask(
                    "group_column_id",
                    "Elige exactamente una variable de grupo y una medida resultado.",
                )
            elif len(profile.group_counts) != 2 or any(g.count < 2 for g in profile.group_counts):
                ask(
                    "groups",
                    "Se requieren exactamente dos grupos con al menos dos casos completos "
                    "cada uno.",
                    "datasets",
                )
            else:
                outcome = outcomes[0]
                limits.append(
                    f"Orden de grupos: {profile.group_counts[0].label} − "
                    f"{profile.group_counts[1].label}, por primera aparición en casos completos."
                )
                if group.measurement_scale.value not in {"nominal", "ordinal"}:
                    ask(
                        "group_column_id",
                        "La variable de grupo debe ser categórica revisada.",
                        "datasets",
                    )
                if i.estimand == "mean_difference" and _quantitative(outcome):
                    technique = (
                        "t_independent" if i.requested_technique == "t_independent" else "t_welch"
                    )
                    if technique == "t_independent":
                        condition(
                            "pooled_variance_justified",
                            "Justifica explícitamente la varianza agrupada; una prueba de "
                            "homogeneidad sola no basta.",
                        )
                elif i.estimand == "distribution_difference" and (
                    _quantitative(outcome) or outcome.measurement_scale.value == "ordinal"
                ):
                    technique = "mann_whitney"
                    limits.append(
                        "Mann–Whitney contrasta distribuciones, no demuestra una diferencia "
                        "de medianas. El efecto de rangos legado es magnitud sin dirección."
                    )
                else:
                    ask(
                        "estimand",
                        "Revisa la pregunta y la escala del resultado. No se cambia una "
                        "comparación de medias por rangos.",
                    )
        elif i.observations.value == "paired":
            if len(selected) != 2 or not i.paired_columns or profile.complete_pair_count is None:
                ask(
                    "paired_columns",
                    "Revisa dos mediciones ordenadas, correspondencia por fila, "
                    "identificación y ausencia de IDs repetidos.",
                )
            elif not all(_quantitative(v) for v in selected):
                ask(
                    "estimand",
                    "Las diferencias pareadas requieren magnitudes cuantitativas "
                    "justificadas; los ordinales no acreditan distancias.",
                )
            elif i.estimand == "mean_difference":
                technique = "t_paired"
            elif i.estimand == "distribution_difference":
                technique = "wilcoxon"
                condition(
                    "difference_symmetry",
                    "Revisa y justifica la simetría de las diferencias para Wilcoxon.",
                )
                limits.append(
                    "Wilcoxon descarta diferencias cero; empates y ceros cambian el método. "
                    "El efecto z/raíz(n) es magnitud sin dirección."
                )
            else:
                ask("estimand", "Aclara si comparas medias o diferencias ordenables con simetría.")
            if profile.complete_case_count < 2:
                ask("cases", "Se requieren al menos dos pares completos.", "datasets")
            if i.paired_columns:
                names = {c.id: c.name for c in ds.columns}
                limits.append(
                    f"Sentido de la diferencia: {names[i.paired_columns.before_column_id]} "
                    f"menos {names[i.paired_columns.after_column_id]}."
                )
    elif i.kind == "reliability":
        ask(
            "instrument",
            "S05 pendiente: revisa instrumento, constructo, ítems recodificados, mapeo y "
            "reglas antes de calcular alfa. No se fabrica un instrumento.",
            "instrument",
        )
    elif i.kind != "descriptive":
        ask("kind", "Selecciona una intención dentro del alcance validado.")
    checks = [c for d in data.diagnostics for c in d.checks]
    if technique in {"pearson", "t_welch", "t_independent", "t_paired"}:
        condition(
            "inference_reviewed",
            "Revisa distribución, extremos y adecuación de la inferencia de "
            "medias/correlación; normalidad sola no decide la técnica.",
        )
        condition(
            "influence_reviewed",
            "Revisa la influencia de extremos y la pertinencia de conservar los casos.",
        )
        if not _confirmed(i.conditions.review_notes) or not i.conditions.review_notes.value:
            ask(
                "conditions/review_notes",
                "Explica la revisión de distribuciones y extremos, y por qué el modelo "
                "responde a la pregunta.",
            )
        needed = {"distribution", "normality", "influence"}
        if not needed.issubset({c.name for c in checks}):
            ask(
                "diagnostics",
                "Solicita distribución, normalidad e influencia del alcance pertinente; "
                "revisa sus límites.",
            )
        adverse = [c for c in checks if c.name in needed and c.status != "compatible"]
        if adverse:
            limits.append(
                "Hay diagnósticos incompatibles o no concluyentes. La justificación humana "
                "queda congelada; no se sustituye la pregunta por rangos."
            )
    if technique in {"spearman", "mann_whitney", "wilcoxon"}:
        condition(
            "influence_reviewed",
            "Revisa extremos, empates y el significado de los rangos/diferencias para esta "
            "pregunta.",
        )
    if i.kind != "descriptive" and data.diagnostics:
        needed = {"complete_cases"}
        if i.kind == "comparison":
            needed.add("paired_cases" if i.observations.value == "paired" else "group_sizes")
        if not needed.issubset({c.name for c in checks if c.status != "not_checked"}):
            ask(
                "diagnostics",
                "Solicita casos completos y los recuentos de grupos/pares pertinentes.",
            )
    # Check real variation without running the final test during proposal.
    complete, _, _ = select_cases(i, ds, dictionary, rows)
    effective = [r for _, r in complete]
    if i.kind != "descriptive" and i.identifier_column_id:
        from app.modules.statistics.diagnostics import _missing

        column = next(c for c in ds.columns if c.id == i.identifier_column_id)
        id_variable = next((v for v in dictionary.variables if column.id in v.column_ids), None)
        ids = [row[column.position] for row, _ in complete]
        if any(
            _missing(value, id_variable.missing_markers if id_variable else []) for value in ids
        ) or len(set(ids)) != len(ids):
            ask(
                "identifier_column_id",
                "Hay identificadores ausentes o repetidos; revisa dependencia y unidad.",
            )
    for role in i.roles:
        variable = next(v for v in selected if v.id == role.variable_id)
        if role.role == "group" and i.group_column_id not in variable.column_ids:
            ask("roles", "El rol de grupo debe corresponder a la columna de grupo elegida.")
        if role.role == "outcome" and i.group_column_id in variable.column_ids:
            ask("roles", "La medida resultado no puede ser la columna de agrupación.")
    if technique in {"pearson", "spearman"} and any(
        len({r[v.column_ids[0]] for r in effective}) < 2 for v in selected
    ):
        ask("variation", "Una variable no tiene variación utilizable.", "datasets")
    if technique in {"t_paired", "wilcoxon"} and i.paired_columns and effective:
        diffs = [
            r[i.paired_columns.before_column_id] - r[i.paired_columns.after_column_id]
            for r in effective
        ]
        if technique == "t_paired" and len(set(diffs)) < 2:
            ask(
                "variation",
                "Las diferencias son constantes: no hay error estándar utilizable.",
                "datasets",
            )
        if technique == "wilcoxon" and sum(d != 0 for d in diffs) < 2:
            ask("variation", "Wilcoxon necesita al menos dos diferencias no nulas.", "datasets")
    if technique in {"t_welch", "t_independent"} and effective:
        out = next(v for v in selected if i.group_column_id not in v.column_ids).column_ids[0]
        if all(
            len({r[out] for r in effective if str(r[i.group_column_id]) == g.label}) < 2
            for g in profile.group_counts
        ):
            ask(
                "variation",
                "Ambos grupos son constantes; no hay error estándar definido.",
                "datasets",
            )
    if i.requested_technique and technique and i.requested_technique != technique:
        ask(
            "requested_technique",
            "La técnica solicitada no responde a esta intención y sus condiciones. Revisa la "
            "solicitud.",
        )
    if questions:
        technique = None
    rationale = (
        f"{technique}: seleccionada por pregunta, escalas y condiciones revisadas. "
        f"{POLICIES[technique]}"
        if technique
        else "Falta evidencia para una elección defendible. "
        "Responde las aclaraciones y solicita una nueva propuesta."
    )
    return Selection(technique, questions, rationale, limits, case_counts(profile, technique))
