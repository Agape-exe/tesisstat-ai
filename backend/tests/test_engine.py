from app.modules.statistics.engine import DeterministicStatisticalEngine
from app.modules.statistics.execution import AnalysisInput
from app.modules.statistics.research_bridge import BytesDatasetReader
from app.shared.contracts import AnalysisPlan, DatasetReference


def _reference() -> DatasetReference:
    return DatasetReference(
        schema_version="1.0.0",
        id="dataset-1",
        location="opaque://research/project-1/dataset-1",
        format="csv",
        row_count=3,
        columns=["score", "group"],
        synthetic=True,
    )


def _plan(
    *, status: str = "approved", technique: str | None = "descriptive_summary"
) -> AnalysisPlan:
    return AnalysisPlan(
        schema_version="1.0.0",
        id="plan-1",
        research_package_id="package-1",
        hypothesis_id="h1",
        dataset_id="dataset-1",
        status=status,
        technique=technique,
        rationale="Resumen descriptivo de las variables seleccionadas.",
    )


def _engine() -> DeterministicStatisticalEngine:
    payload = b"score,group\n10,A\n20,A\n30,B\n"
    return DeterministicStatisticalEngine(
        BytesDatasetReader(lambda _: payload),
        {"dataset-1": _reference()},
    )


def test_engine_executes_approved_descriptive_plan_end_to_end():
    result = _engine().execute(_plan())

    assert result.status == "completed"
    assert result.engine_version == "statistics-engine-v2.0.0"
    metrics = {metric.name: metric.value for metric in result.metrics}
    assert metrics["score.mean"] == 20
    assert metrics["score.sample_variance"] == 100
    assert metrics["group.category.A.percentage"] == 66.66666666666666
    assert result.assumptions[0].status == "passed"


def test_engine_does_not_execute_unapproved_plan():
    result = _engine().execute(_plan(status="proposed"))

    assert result.status == "not_executed"
    assert "aprobado" in result.warnings[0]


def test_engine_requires_selected_columns_for_catalogued_technique():
    result = _engine().execute(_plan(technique="pearson"))

    assert result.status == "failed"
    assert "AnalysisInput" in result.warnings[0]


def test_engine_rejects_unknown_dataset_reference():
    engine = DeterministicStatisticalEngine(
        BytesDatasetReader(lambda _: b"score\n10\n"),
        {},
    )

    result = engine.execute(_plan())

    assert result.status == "failed"
    assert "referencia autorizada" in result.warnings[0]


def test_engine_dispatches_an_allowlisted_pearson_plan_to_analysis_result():
    plan = _plan(technique="pearson")
    engine = DeterministicStatisticalEngine(
        BytesDatasetReader(lambda _: b"score,group\n10,A\n20,A\n30,B\n"),
        {"dataset-1": _reference()},
        {plan.id: AnalysisInput(left=(1, 2, 3, 4), right=(2, 4, 6, 8))},
    )

    result = engine.execute(plan)

    assert result.status == "completed"
    assert {metric.name: metric.value for metric in result.metrics}["r"] == 1
    assert {check.name for check in result.assumptions} >= {"independence", "normality"}
