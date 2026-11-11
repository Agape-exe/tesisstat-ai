"""Deterministic C5 exports. No inferential calculation is imported by a renderer."""

from io import BytesIO

from app.modules.statistics.presentation_v2 import format_number
from app.modules.statistics.reports import (
    authorized_scatter_figure,
    render_pdf_blocks,
)


def figure_lines(figure):
    if figure.kind in {"scatter", "paired", "groups"}:
        # Coordinate geometry only: no new medians, effects or group summaries at export.
        lines = authorized_scatter_figure(
            figure.x_label,
            figure.y_label,
            list(zip(figure.x, figure.y, strict=True)),
            complete_pair_count=figure.total_cases,
            sampled=figure.displayed_cases < figure.total_cases,
        )
        return tuple(
            line.replace("pares completos", "casos completos conjuntos").replace(
                "todos los pares", "todos los casos"
            )
            for line in lines
        )
    maximum = max((abs(v) for v in figure.y), default=0) or 1
    return (
        figure.x_label + " / " + figure.y_label,
        *[
            f"{figure.labels[n] if figure.labels else format_number(x)}: "
            f"{'-' if y < 0 else '+'}{'#' * max(0, round(abs(y) / maximum * 25))} "
            f"{format_number(y)}"
            for n, (x, y) in enumerate(zip(figure.x, figure.y, strict=True))
        ],
    )


def sections(result, display, figures, explanations):
    counts = result.case_counts
    yield (
        "Pregunta y alcance",
        [
            result.question,
            display.technique_label,
            "Variables: " + ", ".join(result.variable_names),
            f"Resultado {result.id}; plan {result.analysis_plan_id}; tabla {result.dataset_id}.",
            f"Estado: {display.status_label}. Vigencia: {result.validity}.",
            f"Casos totales: {counts.total}; utilizados: {counts.used}; "
            f"excluidos: {counts.excluded}.",
            *[f"Grupo {g.label}: {g.count} casos." for g in counts.groups],
            *([f"Pares completos: {counts.pairs}."] if counts.pairs is not None else []),
        ],
    )
    yield (
        "Método y versiones",
        [
            result.engine_version,
            result.method_version,
            f"Fecha UTC: {result.created_at.isoformat()}",
            "Formato: " + display.format_policy,
            "Exportar reproduce cifras guardadas; no recalcula contrastes.",
        ],
    )
    yield (
        "Interpretación básica",
        [display.interpretation_label, display.interpretation or "Sin interpretación concluyente."],
    )
    for explanation in explanations:
        yield (
            "Interpretación IA",
            [
                "Borrador IA pendiente de revisión"
                if explanation.review_status == "draft"
                else "Interpretación IA revisada por el usuario; no certifica validez científica",
                explanation.text,
                "Referencias: " + ", ".join(explanation.metric_keys),
                f"Borrador {explanation.id}, revisión {explanation.revision}.",
            ],
        )
    yield (
        "Supuestos y comprobaciones",
        display.assumptions or ["No se calcularon comprobaciones adicionales."],
    )
    yield (
        "Advertencias y limitaciones",
        [
            *result.warnings,
            *result.limitations,
            *figures.warnings,
            "Significación no equivale a relevancia práctica. Alfa no demuestra validez. "
            "No se establece causalidad.",
        ],
    )
    yield (
        "Fuentes e historial",
        [f"{r.kind}: {r.id}; revisión {r.revision}; SHA256 {r.hash}" for r in result.source_refs],
    )


def render_report(result, display, figures, explanations, format):
    content = list(sections(result, display, figures, explanations))
    metrics = [
        [
            m.label,
            m.formatted + (f" {m.unit}" if m.unit else "") + (f"; {m.reason}" if m.reason else ""),
        ]
        for m in display.metrics
    ]
    tables = [
        ("Métricas guardadas", ["Métrica", "Valor"], metrics),
        *[(t.title, t.columns, t.rows) for t in display.tables],
    ]
    if format in {"txt", "pdf"}:
        blocks = [["TesisStat AI Informe de resultados", ""]]
        for title, paragraphs in content[:2]:
            blocks.append([title, *paragraphs, ""])
        for title, columns, rows in tables:
            heading = [title]
            for n, row in enumerate(rows):
                blocks.append(
                    [
                        *heading,
                        f"Registro {n + 1}",
                        *[f"  {label}: {value}" for label, value in zip(columns, row, strict=True)],
                    ]
                )
                heading = []
            blocks.append([*heading, ""])
        for figure in figures.figures:
            blocks.append([*figure_lines(figure), figure.caption, ""])
        for title, paragraphs in content[2:]:
            blocks.append([title, *paragraphs, ""])
        text = "\n".join(line for block in blocks for line in block)
        return (
            text.encode("utf-8")
            if format == "txt"
            else render_pdf_blocks(
                [
                    [
                        line.translate(str.maketrans({"−": "-", "→": "->", "≤": "<=", "≥": ">="}))
                        for line in block
                    ]
                    for block in blocks
                ]
            )
        )
    from docx import Document
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    document = Document()
    document.sections[0].top_margin = document.sections[0].bottom_margin = Inches(0.7)
    for name in ("Normal", "Title", "Heading 1", "Heading 2"):
        style = document.styles[name]
        style.font.name, style.font.color.rgb = "Calibri", RGBColor(0, 0, 0)
    document.styles["Normal"].font.size = Pt(10)
    document.styles["Normal"].paragraph_format.space_after = Pt(6)
    document.add_paragraph("TesisStat AI Informe de resultados", style="Title")
    for title, paragraphs in content[:2]:
        document.add_heading(title, level=1)
        for p in paragraphs:
            document.add_paragraph(p)
    for title, columns, rows in tables:
        document.add_heading(title, level=1)
        table = document.add_table(rows=1, cols=len(columns))
        table.style = "Table Grid"
        table.autofit = False
        borders = OxmlElement("w:tblBorders")
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            border = OxmlElement(f"w:{side}")
            for name, value in (("val", "single"), ("sz", "4"), ("color", "D9D9D9")):
                border.set(qn(f"w:{name}"), value)
            borders.append(border)
        table._tbl.tblPr.append(borders)
        header = OxmlElement("w:tblHeader")
        table.rows[0]._tr.get_or_add_trPr().append(header)
        for n, label in enumerate(columns):
            table.rows[0].cells[n].text = label
        for row in rows:
            cells = table.add_row().cells
            for cell, value in zip(cells, row, strict=True):
                cell.text = value
        for row_index, row in enumerate(table.rows):
            row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
            for n, cell in enumerate(row.cells):
                cell.width = Inches(3.4 if n == 0 and len(columns) == 2 else 6 / len(columns))
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                if row_index == 0:
                    shading = OxmlElement("w:shd")
                    shading.set(qn("w:fill"), "E5EEF5")
                    cell._tc.get_or_add_tcPr().append(shading)
                    for run in cell.paragraphs[0].runs:
                        run.bold = True
        document.add_paragraph()
    for n, figure in enumerate(figures.figures):
        document.add_heading(f"Figura {n + 1}", level=2)
        for line in figure_lines(figure):
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.keep_with_next = True
            run = paragraph.add_run(line)
            run.font.name, run.font.size = "Courier New", Pt(8)
        document.add_paragraph(figure.caption).paragraph_format.keep_together = True
    for title, paragraphs in content[2:]:
        document.add_heading(title, level=1)
        for n, p in enumerate(paragraphs):
            # Break long hashes/IDs explicitly rather than shrink report text.
            paragraph = document.add_paragraph(p.replace("SHA256 ", "SHA256\n"))
            paragraph.paragraph_format.keep_together = True
            if title in {"Interpretación IA", "Interpretación básica"}:
                paragraph.paragraph_format.keep_with_next = n < len(paragraphs) - 1
    output = BytesIO()
    for element in (document.element, document.styles.element):
        for border in element.xpath(".//w:pBdr"):
            border.getparent().remove(border)
    document.save(output)
    return output.getvalue()
