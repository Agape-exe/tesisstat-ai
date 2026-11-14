from pytest import raises

from app.modules.statistics.catalog import list_techniques
from app.modules.statistics.planner import DeterministicStatisticalPlanner, UnknownHypothesis
from app.shared.contracts import (
    DatasetReference,
    ResearchHypothesis,
    ResearchPackage,
    ResearchVariable,
)


def _package(
    *,
    hypothesis: ResearchHypothesis,
    variables: list[ResearchVariable],
    observations: str = "independent",
    methodology_status: str = "reviewed",
) -> ResearchPackage:
    return ResearchPackage(
        schema_version="1.0.0",
        id="package-1",
        title="Investigación sintética",
        methodology_status=methodology_status,
        design="observational",
        observations=observations,
        sampling_notes="Muestra sintética",
        variables=variables,
        hypotheses=[hypothesis],
        dataset=DatasetReference(
            schema_version="1.0.0",
            id="dataset-1",
            location="opaque://research/project-1/dataset-1",
            format="csv",
            row_count=4,
            columns=["x", "y", "group", "covariate"],
            synthetic=True,
        ),
    )


def test_catalog_contains_the_eighteen_planned_inferential_techniques():
    techniques = list_techniques()

    assert len(techniques) == 19  # 18 inferential techniques plus descriptives.
    assert sum(technique.group != "descriptive" for technique in techniques) == 18
    assert len({technique.name for technique in techniques}) == len(techniques)


def test_planner_selects_pearson_for_two_quantitative_association_variables():
    variables = [
        ResearchVariable(
            schema_version="1.0.0",
            id="x",
            name="X",
            role="independent",
            measurement_scale="ratio",
            columns=["x"],
        ),
        ResearchVariable(
            schema_version="1.0.0",
            id="y",
            name="Y",
            role="dependent",
            measurement_scale="interval",
            columns=["y"],
        ),
    ]
    hypothesis = ResearchHypothesis(
        schema_version="1.0.0",
        id="h1",
        statement="X se asocia con Y",
        objective="Medir asociación",
        kind="association",
        variable_ids=["x", "y"],
    )

    plan = DeterministicStatisticalPlanner().propose(
        _package(hypothesis=hypothesis, variables=variables), "h1"
    )

    assert plan.status == "proposed"
    assert plan.technique == "pearson"
    assert "Linealidad" in plan.assumptions_to_check


def test_planner_requests_group_count_for_independent_comparison():
    variables = [
        ResearchVariable(
            schema_version="1.0.0",
            id="group",
            name="Grupo",
            role="independent",
            measurement_scale="nominal",
            columns=["group"],
        ),
        ResearchVariable(
            schema_version="1.0.0",
            id="y",
            name="Resultado",
            role="dependent",
            measurement_scale="ratio",
            columns=["y"],
        ),
    ]
    hypothesis = ResearchHypothesis(
        schema_version="1.0.0",
        id="h1",
        statement="El resultado difiere por grupo",
        objective="Comparar grupos",
        kind="comparison",
        variable_ids=["group", "y"],
    )

    plan = DeterministicStatisticalPlanner().propose(
        _package(hypothesis=hypothesis, variables=variables), "h1"
    )

    assert plan.status == "needs_clarification"
    assert plan.technique is None
    assert any("grupos" in question for question in plan.pending_questions)


def test_planner_selects_paired_nonparametric_test_for_ordinal_observations():
    variables = [
        ResearchVariable(
            schema_version="1.0.0",
            id="pre",
            name="Pre",
            role="independent",
            measurement_scale="ordinal",
            columns=["x"],
        ),
        ResearchVariable(
            schema_version="1.0.0",
            id="post",
            name="Post",
            role="dependent",
            measurement_scale="ordinal",
            columns=["y"],
        ),
    ]
    hypothesis = ResearchHypothesis(
        schema_version="1.0.0",
        id="h1",
        statement="La medición cambia",
        objective="Comparar mediciones",
        kind="comparison",
        variable_ids=["pre", "post"],
    )

    plan = DeterministicStatisticalPlanner().propose(
        _package(hypothesis=hypothesis, variables=variables, observations="paired"), "h1"
    )

    assert plan.status == "proposed"
    assert plan.technique == "wilcoxon"


def test_planner_selects_ancova_for_group_outcome_and_covariate():
    variables = [
        ResearchVariable(
            schema_version="1.0.0",
            id="group",
            name="Grupo",
            role="independent",
            measurement_scale="nominal",
            columns=["group"],
        ),
        ResearchVariable(
            schema_version="1.0.0",
            id="covariate",
            name="Covariable",
            role="covariate",
            measurement_scale="ratio",
            columns=["covariate"],
        ),
        ResearchVariable(
            schema_version="1.0.0",
            id="y",
            name="Resultado",
            role="dependent",
            measurement_scale="ratio",
            columns=["y"],
        ),
    ]
    hypothesis = ResearchHypothesis(
        schema_version="1.0.0",
        id="h1",
        statement="El resultado difiere por grupo al ajustar por covariable.",
        objective="Comparar grupos ajustados.",
        kind="comparison",
        variable_ids=["group", "covariate", "y"],
    )

    plan = DeterministicStatisticalPlanner().propose(
        _package(hypothesis=hypothesis, variables=variables), "h1"
    )

    assert plan.status == "proposed"
    assert plan.technique == "ancova"


def test_planner_requires_review_and_rejects_unknown_hypothesis():
    variable = ResearchVariable(
        schema_version="1.0.0",
        id="x",
        name="X",
        role="descriptive",
        measurement_scale="ratio",
        columns=["x"],
    )
    hypothesis = ResearchHypothesis(
        schema_version="1.0.0",
        id="h1",
        statement="X se describe",
        objective="Describir X",
        kind="descriptive",
        variable_ids=["x"],
    )
    package = _package(
        hypothesis=hypothesis,
        variables=[variable],
        methodology_status="draft",
    )
    planner = DeterministicStatisticalPlanner()

    plan = planner.propose(package, "h1")

    assert plan.status == "needs_clarification"
    assert plan.pending_questions
    with raises(UnknownHypothesis):
        planner.propose(package, "missing")
