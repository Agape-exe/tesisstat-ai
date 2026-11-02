from app.modules.statistics.reports import render_docx, render_pdf, render_text
from app.shared.contracts import AnalysisResult, AssumptionCheck, Metric


def result() -> AnalysisResult:
    return AnalysisResult(
        schema_version="1.0.0",
        id="result-demo",
        analysis_plan_id="plan-demo",
        dataset_id="dataset-demo",
        status="completed",
        metrics=[Metric(name="x.mean", value=2.5)],
        assumptions=[AssumptionCheck(name="normality", status="passed", details="OK")],
        warnings=["Advertencia de prueba"],
        engine_version="statistics-engine-v1",
        interpretation="Resumen determinista.",
    )


def test_text_report_contains_result_sections() -> None:
    rendered = render_text(result())
    assert "Métricas" in rendered
    assert "x.mean: 2.5" in rendered
    assert "Advertencia de prueba" in rendered


def test_docx_report_is_valid_zip() -> None:
    assert render_docx(result()).startswith(b"PK")


def test_pdf_report_has_pdf_signature_and_eof() -> None:
    rendered = render_pdf(result())
    assert rendered.startswith(b"%PDF-1.4")
    assert rendered.rstrip().endswith(b"%%EOF")
