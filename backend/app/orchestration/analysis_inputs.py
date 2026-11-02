"""Adapt verified two-column association techniques, without formulas."""

from fastapi import HTTPException

from app.modules.statistics.datasets import DatasetTable
from app.modules.statistics.execution import AnalysisInput
from app.shared.contracts import AnalysisPlan, ResearchPackage

TWO_GROUP_TECHNIQUES = {"t_independent", "t_welch", "mann_whitney"}
MULTI_GROUP_TECHNIQUES = {"anova", "anova_welch", "kruskal_wallis"}
POSTHOC_TECHNIQUES = {"tukey", "games_howell"}
GROUP_TECHNIQUES = TWO_GROUP_TECHNIQUES | MULTI_GROUP_TECHNIQUES | POSTHOC_TECHNIQUES

CONNECTED = {
    "descriptive_summary",
    "pearson",
    "spearman",
    "chi_square",
    "fisher_exact",
    "t_paired",
    "wilcoxon",
    "t_independent",
    "mann_whitney",
    "cronbach_alpha",
    "t_welch",
    "anova",
    "anova_welch",
    "kruskal_wallis",
    "tukey",
    "games_howell",
}


def pearson_questions(package: ResearchPackage, hypothesis_id: str) -> list[str]:
    hypothesis = next(item for item in package.hypotheses if item.id == hypothesis_id)
    variables = {item.id: item for item in package.variables}
    selected = [variables[item] for item in hypothesis.variable_ids]
    questions = []
    if package.design == "unknown":
        questions.append("Confirma el diseño de investigación en las vinculaciones.")
    if package.observations != "independent":
        questions.append("Este adaptador Pearson requiere observaciones independientes declaradas.")
    if any(item.role == "unknown" for item in selected):
        questions.append("Confirma los roles de las variables en las vinculaciones.")
    if len(selected) != 2 or any(len(item.columns) != 1 for item in selected):
        questions.append("Pearson requiere dos variables, cada una vinculada a una única columna.")
    elif selected[0].columns == selected[1].columns:
        questions.append("Vincula las variables Pearson a dos columnas distintas.")
    return questions


def spearman_questions(package: ResearchPackage, hypothesis_id: str) -> list[str]:
    """Return methodological questions required before a Spearman analysis."""
    questions = pearson_questions(package, hypothesis_id)
    if package.observations != "independent":
        return questions
    variables = {item.id: item for item in package.variables}
    selected = [
        variables[item]
        for item in next(
            item for item in package.hypotheses if item.id == hypothesis_id
        ).variable_ids
    ]
    if any(item.measurement_scale not in {"ordinal", "interval", "ratio"} for item in selected):
        questions.append("Spearman requiere escalas ordinales, intervalares o de razón.")
    return questions


def categorical_association_questions(package: ResearchPackage, hypothesis_id: str) -> list[str]:
    """Validate the Research metadata needed by categorical associations."""
    questions = pearson_questions(package, hypothesis_id)
    variables = {item.id: item for item in package.variables}
    hypothesis = next(item for item in package.hypotheses if item.id == hypothesis_id)
    selected = [variables[item] for item in hypothesis.variable_ids]
    if any(item.measurement_scale not in {"nominal", "ordinal"} for item in selected):
        questions.append("La asociación categórica requiere escalas nominales u ordinales.")
    return questions


def paired_questions(package: ResearchPackage, hypothesis_id: str) -> list[str]:
    """Validate metadata for paired numeric or ordinal comparisons."""
    questions = pearson_questions(package, hypothesis_id)
    if package.observations not in {"paired", "repeated"}:
        questions.append("La comparación pareada requiere observaciones emparejadas o repetidas.")
    return [question for question in questions if "observaciones independientes" not in question]


def independent_questions(package: ResearchPackage, hypothesis_id: str) -> list[str]:
    """Validate metadata for independent-group comparisons."""
    hypothesis = next(item for item in package.hypotheses if item.id == hypothesis_id)
    variables = {item.id: item for item in package.variables}
    selected = [variables[item] for item in hypothesis.variable_ids]
    questions: list[str] = []
    if package.design == "unknown":
        questions.append("Confirma el diseño de investigación en las vinculaciones.")
    if package.observations != "independent":
        questions.append(
            "La comparación independiente requiere observaciones independientes declaradas."
        )
    if len(selected) != 2 or any(len(item.columns) != 1 for item in selected):
        questions.append(
            "La comparación independiente requiere dos variables con una columna cada una."
        )
        return questions
    dependents = [item for item in selected if item.role == "dependent"]
    groups = [item for item in selected if item.role == "independent"]
    if len(dependents) != 1 or len(groups) != 1:
        questions.append("Identifica una variable dependiente y una variable de agrupación.")
    else:
        if dependents[0].measurement_scale not in {"ordinal", "interval", "ratio"}:
            questions.append(
                "La variable dependiente debe tener escala ordinal, intervalar o de razón."
            )
        if groups[0].measurement_scale not in {"nominal", "ordinal"}:
            questions.append("La variable de agrupación debe tener escala nominal u ordinal.")
        if dependents[0].columns == groups[0].columns:
            questions.append("Vincula la agrupación y el resultado a columnas distintas.")
    return questions


def reliability_questions(package: ResearchPackage, hypothesis_id: str) -> list[str]:
    """Validate item-column metadata for a Cronbach reliability analysis."""
    hypothesis = next(item for item in package.hypotheses if item.id == hypothesis_id)
    variables = {item.id: item for item in package.variables}
    selected = [variables[item] for item in hypothesis.variable_ids]
    columns = [column for variable in selected for column in variable.columns]
    questions: list[str] = []
    if len(columns) < 2:
        questions.append("Alfa de Cronbach requiere al menos dos columnas de ítems.")
    if len(columns) != len(set(columns)):
        questions.append("Las columnas de ítems para Alfa de Cronbach no pueden repetirse.")
    if any(
        variable.measurement_scale not in {"ordinal", "interval", "ratio"} for variable in selected
    ):
        questions.append("Los ítems deben tener escala ordinal, intervalar o de razón.")
    return questions


def analysis_input(
    package: ResearchPackage, plan: AnalysisPlan, table: DatasetTable
) -> AnalysisInput:
    questions = {
        "pearson": pearson_questions,
        "spearman": spearman_questions,
        "chi_square": categorical_association_questions,
        "fisher_exact": categorical_association_questions,
        "t_paired": paired_questions,
        "wilcoxon": paired_questions,
        "t_independent": independent_questions,
        "t_welch": independent_questions,
        "mann_whitney": independent_questions,
        "anova": independent_questions,
        "anova_welch": independent_questions,
        "kruskal_wallis": independent_questions,
        "tukey": independent_questions,
        "games_howell": independent_questions,
        "cronbach_alpha": reliability_questions,
    }.get(plan.technique, lambda *_: ["La técnica no admite esta entrada de dos columnas."])(
        package, plan.hypothesis_id
    )
    if questions:
        raise HTTPException(409, "Las vinculaciones no permiten construir la entrada solicitada.")
    hypothesis = next(item for item in package.hypotheses if item.id == plan.hypothesis_id)
    variables = {item.id: item for item in package.variables}
    selected = [variables[item] for item in hypothesis.variable_ids]
    allowed = {
        "pearson": {"interval", "ratio"},
        "spearman": {"ordinal", "interval", "ratio"},
        "chi_square": {"nominal", "ordinal"},
        "fisher_exact": {"nominal", "ordinal"},
        "t_paired": {"interval", "ratio"},
        "wilcoxon": {"ordinal", "interval", "ratio"},
        "t_independent": {"interval", "ratio"},
        "t_welch": {"interval", "ratio"},
        "mann_whitney": {"ordinal", "interval", "ratio"},
        "anova": {"interval", "ratio"},
        "anova_welch": {"interval", "ratio"},
        "kruskal_wallis": {"ordinal", "interval", "ratio"},
        "tukey": {"interval", "ratio"},
        "games_howell": {"interval", "ratio"},
        "cronbach_alpha": {"ordinal", "interval", "ratio"},
    }.get(plan.technique, set())
    if plan.technique == "cronbach_alpha":
        columns = [column for item in selected for column in item.columns]
        try:
            indices = [table.columns.index(column) for column in columns]
        except ValueError as exc:
            raise HTTPException(409, "Una columna de ítem vinculada ya no existe.") from exc
        return AnalysisInput(
            matrix=tuple(tuple(row[index] for index in indices) for row in table.rows)
        )
    if plan.technique in GROUP_TECHNIQUES:
        group_variable = next(item for item in selected if item.role == "independent")
        outcome_variable = next(item for item in selected if item.role == "dependent")
        if (
            group_variable.measurement_scale not in {"nominal", "ordinal"}
            or outcome_variable.measurement_scale not in allowed
        ):
            raise HTTPException(409, "La técnica requiere escalas de medición confirmadas.")
    elif any(item.measurement_scale not in allowed for item in selected):
        raise HTTPException(409, "La técnica requiere escalas de medición confirmadas.")
    if plan.technique in GROUP_TECHNIQUES:
        group_variable = next(item for item in selected if item.role == "independent")
        outcome_variable = next(item for item in selected if item.role == "dependent")
        try:
            group_index = table.columns.index(group_variable.columns[0])
            outcome_index = table.columns.index(outcome_variable.columns[0])
        except ValueError as exc:
            raise HTTPException(409, "Una columna vinculada ya no existe.") from exc
        groups: dict[str, list[object]] = {}
        for row in table.rows:
            label, value = row[group_index], row[outcome_index]
            if label is None or value is None:
                continue
            groups.setdefault(label, []).append(value)
        if plan.technique in TWO_GROUP_TECHNIQUES and len(groups) != 2:
            raise HTTPException(
                409, "La comparación independiente requiere exactamente dos grupos."
            )
        if plan.technique in MULTI_GROUP_TECHNIQUES and len(groups) < 3:
            raise HTTPException(409, "La comparación multigrupo requiere tres o más grupos.")
        if plan.technique in POSTHOC_TECHNIQUES and len(groups) < 3:
            raise HTTPException(409, "La comparación post-hoc requiere tres o más grupos.")
        values = tuple(tuple(group) for group in groups.values())
        labels = tuple(groups)
        if plan.technique in TWO_GROUP_TECHNIQUES:
            left, right = values
            return AnalysisInput(left=left, right=right, groups=values, labels=labels)
        return AnalysisInput(groups=values, labels=labels)
    try:
        left, right = [table.columns.index(item.columns[0]) for item in selected]
    except ValueError as exc:
        raise HTTPException(409, "Una columna vinculada ya no existe.") from exc
    # Preserve every row and missing value. Statistics owns complete-pair validation.
    return AnalysisInput(
        left=tuple(row[left] for row in table.rows),
        right=tuple(row[right] for row in table.rows),
    )
