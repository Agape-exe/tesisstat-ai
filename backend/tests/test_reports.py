from app.modules.statistics.reports import (
    authorized_scatter_figure,
    render_docx,
    render_pdf,
    render_text,
)
from app.shared.contracts import AnalysisResult, AssumptionCheck, Metric


def result() -> AnalysisResult:
    return AnalysisResult(
        schema_version="1.0.0",
        id="result-demo",
        analysis_plan_id="plan-demo",
        dataset_id="dataset-demo",
        status="completed",
        metrics=[
            Metric(name="x.mean", value=2.5),
            Metric(name="r", value=0.8),
            Metric(name="p_value", value=0.032),
        ],
        assumptions=[AssumptionCheck(name="normality", status="passed", details="OK")],
        warnings=["Advertencia de prueba"],
        engine_version="statistics-engine-v1",
        interpretation="Resumen determinista.",
    )


def test_text_report_contains_result_sections() -> None:
    rendered = render_text(result())
    assert "Metadatos de reproducibilidad" in rendered
    assert "Plan de análisis: plan-demo" in rendered
    assert "Tabla 1. Métricas calculadas" in rendered
    assert "Tabla 2. Verificación de supuestos" in rendered
    assert "x.mean: 2.5" in rendered
    assert "Figura 1. Resumen gráfico de métricas persistidas" in rendered
    assert "Asociaciones y efectos (escala -1 a 1)" in rendered
    assert "P-valores (escala 0 a 1; referencia alfa=0.05)" in rendered
    assert "no determina significancia automáticamente" in rendered
    assert "Advertencia de prueba" in rendered


def test_docx_report_is_valid_zip() -> None:
    assert render_docx(result()).startswith(b"PK")


def test_docx_report_has_numbered_tables_and_methodological_context() -> None:
    from io import BytesIO

    from docx import Document

    document = Document(BytesIO(render_docx(result(), context=("Diseño transversal.",))))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Metadatos de reproducibilidad" in text
    assert "Contexto metodológico" in text
    assert "Tabla 1. Métricas calculadas" in text
    assert "Figura 1. Resumen gráfico de métricas persistidas" in text
    assert "Tabla 2. Verificación de supuestos" in text
    assert len(document.tables) == 2
    assert document.tables[1].rows[0].cells[1].text == "Estado"


def test_reports_omit_figure_when_metrics_have_no_supported_scale():
    report = result()
    report.metrics = [Metric(name="x.mean", value=2.5)]

    assert "Figura 1." not in render_text(report)


def test_reports_render_authorized_observation_figure_after_persisted_metrics():
    figure = authorized_scatter_figure(
        "horas",
        "nota",
        [(1.0, 2.0), (2.0, 4.0), (3.0, 6.0)],
        complete_pair_count=3,
        sampled=False,
    )
    text = render_text(result(), observation_figures=(figure,))
    assert "Figura 2. Dispersión autorizada: horas y nota" in text
    assert "Eje X: horas (1 a 3)" in text
    assert "3 pares completos; se representan 3 pares" in text
    assert "figura descriptiva; no determina significancia automáticamente" in text


def test_pdf_report_has_pdf_signature_and_eof() -> None:
    rendered = render_pdf(result())
    assert rendered.startswith(b"%PDF-1.4")
    assert rendered.rstrip().endswith(b"%%EOF")


def test_pdf_report_preserves_persisted_metric_figure():
    from io import BytesIO

    from pypdf import PdfReader

    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(render_pdf(result()))).pages)

    assert "Figura 1. Resumen gráfico de métricas persistidas" in text
    assert "referencia alfa=0.05" in text
    assert "no determina significancia automáticamente" in text


def test_reports_preserve_spanish_long_content_and_pdf_literals():
    from io import BytesIO

    from docx import Document
    from pypdf import PdfReader

    report = result()
    report.warnings = [
        f"Línea {i}: análisis, correlación, niño, pingüino (a&b < c) \\ fin." for i in range(120)
    ]
    report.interpretation = "última conclusión: " + "dato" * 90
    pdf = PdfReader(BytesIO(render_pdf(report)), strict=True)
    assert len(pdf.pages) >= 3
    text = "\n".join(page.extract_text() for page in pdf.pages)
    assert "Línea 119" in text
    assert "análisis, correlación, niño, pingüino (a&b < c) \\ fin." in text
    assert "última conclusión" in text
    assert "dato" * 90 in "".join(text.split())
    doc = Document(BytesIO(render_docx(report)))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert report.warnings[-1] in text
    assert report.interpretation in text


def test_pdf_discloses_unicode_limit_and_docx_preserves_it():
    from io import BytesIO

    from docx import Document
    from pypdf import PdfReader

    report = result()
    report.warnings = ["Símbolo no WinAnsi: 漢"]
    pdf = PdfReader(BytesIO(render_pdf(report)), strict=True)
    text = "\n".join(page.extract_text() for page in pdf.pages)
    assert "Limitación PDF" in text
    assert "Descarga DOCX" in text
    assert "WinAnsi: ?" in text
    assert report.warnings[0] in "\n".join(
        p.text for p in Document(BytesIO(render_docx(report))).paragraphs
    )
