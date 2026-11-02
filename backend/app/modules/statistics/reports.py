"""Deterministic report renderers for completed statistical analyses.

The module deliberately keeps rendering separate from calculation.  DOCX uses
the already-approved ``python-docx`` dependency and PDF is a small, dependency-
free text report suitable for the development/demo flow.
"""

from __future__ import annotations

from html import escape

from app.shared.contracts import AnalysisResult


def render_text(result: AnalysisResult) -> str:
    lines = [
        "TesisStat AI — Informe estadístico",
        f"Resultado: {result.id}",
        f"Estado: {result.status}",
        f"Motor: {result.engine_version}",
        "",
        "Métricas",
    ]
    if result.metrics:
        lines.extend(f"- {metric.name}: {metric.value:.6g}" for metric in result.metrics)
    else:
        lines.append("- No hay métricas disponibles.")
    lines.append("")
    lines.append("Supuestos")
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


def render_docx(result: AnalysisResult) -> bytes:
    from io import BytesIO

    from docx import Document

    document = Document()
    document.add_heading("TesisStat AI — Informe estadístico", level=1)
    document.add_paragraph(f"Resultado: {result.id}")
    document.add_paragraph(f"Estado: {result.status} · Motor: {result.engine_version}")
    document.add_heading("Métricas", level=2)
    table = document.add_table(rows=1, cols=2)
    table.style = "Light Shading Accent 1"
    table.rows[0].cells[0].text = "Métrica"
    table.rows[0].cells[1].text = "Valor"
    for metric in result.metrics:
        cells = table.add_row().cells
        cells[0].text = metric.name
        cells[1].text = f"{metric.value:.6g}"
    document.add_heading("Supuestos", level=2)
    for assumption in result.assumptions:
        document.add_paragraph(
            f"{assumption.name}: {assumption.status} — {assumption.details}", style="List Bullet"
        )
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


def render_pdf(result: AnalysisResult) -> bytes:
    """Render a compact single-page PDF without adding a scientific dependency."""
    text = render_text(result).splitlines()
    commands = ["BT", "/F1 10 Tf", "50 760 Td"]
    for index, line in enumerate(text[:48]):
        safe = escape(line).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            commands.append("0 -14 Td")
        commands.append(f"({safe}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
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
