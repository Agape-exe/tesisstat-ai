"""Adapt only the two verified techniques, without statistical formulas."""

from fastapi import HTTPException

from app.modules.statistics.datasets import DatasetTable
from app.modules.statistics.execution import AnalysisInput
from app.shared.contracts import AnalysisPlan, ResearchPackage

CONNECTED = {"descriptive_summary", "pearson"}


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


def analysis_input(
    package: ResearchPackage, plan: AnalysisPlan, table: DatasetTable
) -> AnalysisInput:
    if plan.technique != "pearson" or pearson_questions(package, plan.hypothesis_id):
        raise HTTPException(409, "Las vinculaciones no permiten construir la entrada Pearson.")
    hypothesis = next(item for item in package.hypotheses if item.id == plan.hypothesis_id)
    variables = {item.id: item for item in package.variables}
    selected = [variables[item] for item in hypothesis.variable_ids]
    if any(item.measurement_scale not in {"interval", "ratio"} for item in selected):
        raise HTTPException(409, "Pearson requiere escalas cuantitativas confirmadas.")
    try:
        left, right = [table.columns.index(item.columns[0]) for item in selected]
    except ValueError as exc:
        raise HTTPException(409, "Una columna vinculada ya no existe.") from exc
    # Preserve every row and missing value. Statistics owns complete-pair validation.
    return AnalysisInput(
        left=tuple(row[left] for row in table.rows),
        right=tuple(row[right] for row in table.rows),
    )
