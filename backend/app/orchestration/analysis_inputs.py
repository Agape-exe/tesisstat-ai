"""Adapt verified two-column association techniques, without formulas."""

from fastapi import HTTPException

from app.modules.statistics.datasets import DatasetTable
from app.modules.statistics.execution import AnalysisInput
from app.shared.contracts import AnalysisPlan, ResearchPackage

CONNECTED = {
    "descriptive_summary",
    "pearson",
    "spearman",
    "chi_square",
    "fisher_exact",
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


def analysis_input(
    package: ResearchPackage, plan: AnalysisPlan, table: DatasetTable
) -> AnalysisInput:
    questions = {
        "pearson": pearson_questions,
        "spearman": spearman_questions,
        "chi_square": categorical_association_questions,
        "fisher_exact": categorical_association_questions,
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
    }.get(plan.technique, set())
    if any(item.measurement_scale not in allowed for item in selected):
        raise HTTPException(409, "La técnica requiere escalas de medición confirmadas.")
    try:
        left, right = [table.columns.index(item.columns[0]) for item in selected]
    except ValueError as exc:
        raise HTTPException(409, "Una columna vinculada ya no existe.") from exc
    # Preserve every row and missing value. Statistics owns complete-pair validation.
    return AnalysisInput(
        left=tuple(row[left] for row in table.rows),
        right=tuple(row[right] for row in table.rows),
    )
