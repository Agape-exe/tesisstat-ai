"""Deterministic report renderers for completed statistical analyses.

The module deliberately keeps rendering separate from calculation.  DOCX uses
the already-approved ``python-docx`` dependency and PDF is a small, dependency-
free text report suitable for the development/demo flow.
"""

from __future__ import annotations

from textwrap import wrap

from app.shared.contracts import AnalysisResult


def _metadata_lines(result: AnalysisResult) -> tuple[str, ...]:
    """Keep the minimum reproducibility metadata with every export."""

    return (
        f"Resultado: {result.id}",
        f"Plan de análisis: {result.analysis_plan_id}",
        f"Dataset: {result.dataset_id}",
        f"Estado: {result.status}",
        f"Esquema: {result.schema_version}",
        f"Motor: {result.engine_version}",
    )


def render_text(result: AnalysisResult, *, context: tuple[str, ...] = ()) -> str:
    lines = [
        "TesisStat AI — Informe estadístico",
        "",
        "Metadatos de reproducibilidad",
        *_metadata_lines(result),
    ]
    if context:
        lines.extend(
            [
                "",
                "Contexto metodológico",
                *context,
            ]
        )
    lines.extend(
        [
            "",
            "Tabla 1. Métricas calculadas",
        ]
    )
    if result.metrics:
        lines.extend(f"- {metric.name}: {metric.value:.6g}" for metric in result.metrics)
    else:
        lines.append("- No hay métricas disponibles.")
    lines.extend(["", "Tabla 2. Verificación de supuestos"])
    if result.assumptions:
        lines.extend(
            f"- {item.name}: {item.status} — {item.details}" for item in result.assumptions
        )
    else:
        lines.append("- No se evaluaron supuestos.")
    if result.warnings:
        lines.extend(["", "Advertencias"])
        lines.extend(f"- {warning}" for warning in result.warnings)
    if result.interpretation:
        lines.extend(["", "Interpretación", result.interpretation])
    return "\n".join(lines) + "\n"


def render_docx(result: AnalysisResult, *, context: tuple[str, ...] = ()) -> bytes:
    from io import BytesIO

    from docx import Document
    from docx.shared import RGBColor

    document = Document()
    for style_name in ("Title", "Heading 1", "Heading 2"):
        document.styles[style_name].font.color.rgb = RGBColor(0, 0, 0)
    document.add_heading("TesisStat AI Informe Estadistico", level=0)
    document.add_heading("Metadatos de reproducibilidad", level=2)
    for line in _metadata_lines(result):
        document.add_paragraph(line)
    if context:
        document.add_heading("Contexto metodológico", level=2)
        for line in context:
            document.add_paragraph(line)
    document.add_heading("Tabla 1. Métricas calculadas", level=2)
    table = document.add_table(rows=1, cols=2)
    table.style = "Light Shading Accent 1"
    table.rows[0].cells[0].text = "Métrica"
    table.rows[0].cells[1].text = "Valor"
    for metric in result.metrics:
        cells = table.add_row().cells
        cells[0].text = metric.name
        cells[1].text = f"{metric.value:.6g}"
    document.add_heading("Tabla 2. Verificación de supuestos", level=2)
    assumptions = document.add_table(rows=1, cols=3)
    assumptions.style = "Light Shading Accent 1"
    assumptions.rows[0].cells[0].text = "Supuesto"
    assumptions.rows[0].cells[1].text = "Estado"
    assumptions.rows[0].cells[2].text = "Detalle"
    for assumption in result.assumptions:
        cells = assumptions.add_row().cells
        cells[0].text = assumption.name
        cells[1].text = assumption.status
        cells[2].text = assumption.details
    if result.warnings:
        document.add_heading("Advertencias", level=2)
        for warning in result.warnings:
            document.add_paragraph(warning, style="List Bullet")
    if result.interpretation:
        document.add_heading("Interpretación", level=2)
        document.add_paragraph(result.interpretation)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def render_pdf(result: AnalysisResult, *, context: tuple[str, ...] = ()) -> bytes:
    """Paginated plain-text PDF. WinAnsi supports Spanish, but not full Unicode.

    Unsupported glyphs are explicitly disclosed and replaced; DOCX retains Unicode.
    Keep byte offsets exact, wrap long tokens and never truncate report content.
    """
    report = render_text(result, context=context)
    try:
        report.encode("cp1252")
    except UnicodeEncodeError:
        report += (
            "\nLimitación PDF: caracteres fuera de WinAnsi se sustituyen por ?. "
            "Descarga DOCX para conservar Unicode completo.\n"
        )
    lines = [part for line in report.splitlines() for part in (wrap(line, 82) or [""])]
    pages = [lines[start : start + 49] for start in range(0, len(lines), 49)]
    kids = " ".join(f"{4 + index * 2} 0 R" for index in range(len(pages)))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>",
    ]
    for index, page in enumerate(pages):
        commands = ["BT", "/F1 10 Tf", "50 750 Td"]
        for number, line in enumerate(page):
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            if number:
                commands.append("0 -14 Td")
            commands.append(f"({safe}) Tj")
        commands.extend(
            ["ET", "BT", "/F1 9 Tf", "50 35 Td", f"({index + 1}/{len(pages)}) Tj", "ET"]
        )
        stream = "\n".join(commands).encode("cp1252", errors="replace")
        objects.extend(
            [
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + index * 2} 0 R >>"
                ).encode(),
                b"<< /Length "
                + str(len(stream)).encode()
                + b" >>\nstream\n"
                + stream
                + b"\nendstream",
            ]
        )
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(output)
