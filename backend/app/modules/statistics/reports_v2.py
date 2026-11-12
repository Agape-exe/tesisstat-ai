"""Deterministic reports over persisted metrics and authorized figure payloads."""

from io import BytesIO
from xml.sax.saxutils import escape

from app.modules.statistics.report_charts_v2 import chart_drawing, chart_png


def sections(result, display, figures, explanations):
    counts = result.case_counts
    yield (
        "Qué se analizó",
        [
            result.question,
            display.technique_label,
            "Variables: " + ", ".join(result.variable_names),
            f"Casos totales: {counts.total}; utilizados: {counts.used}; "
            f"excluidos: {counts.excluded}.",
            *[f"Grupo {g.label}: {g.count} casos." for g in counts.groups],
            *([f"Pares completos: {counts.pairs}."] if counts.pairs is not None else []),
        ],
    )
    yield (
        "Interpretación y hallazgos",
        [
            display.interpretation or "Sin interpretación concluyente.",
            display.interpretation_label,
        ],
    )
    for explanation in explanations:
        if explanation.evidence_policy != "structured-findings-v1":
            yield (
                "Interpretación histórica no verificada",
                [
                    "Se conserva en el historial. Su prosa no se exporta porque no se verificó "
                    "el respaldo de cada hallazgo."
                ],
            )
            continue
        yield (
            "Interpretación IA",
            [
                "Borrador IA pendiente de revisión"
                if explanation.review_status == "draft"
                else "Interpretación IA revisada por el usuario; no certifica validez científica",
                "Conceptos y comentarios generales: " + explanation.text,
                "Hallazgos reproducidos por el servidor: "
                + (explanation.grounded_text or "Sin hallazgos verificados."),
            ],
        )
    applicable = [
        text
        for check, text in zip(result.assumptions, display.assumptions, strict=True)
        if check.status != "not_checked"
    ]
    if applicable:
        yield "Comprobaciones pertinentes", applicable
    limits = list(dict.fromkeys([*display.limitations, *figures.warnings]))
    if limits:
        yield "Alcance y limitaciones", limits
    methodological = [
        w
        for w in result.warnings
        if result.technique == "descriptive_summary" and "cuantiles tipo 7" in w
    ]
    warnings = [w for w in result.warnings if w not in methodological]
    if warnings:
        yield "Observaciones del cálculo", list(dict.fromkeys(warnings))
    yield (
        "Anexo técnico",
        [
            f"Resultado {result.id}; plan {result.analysis_plan_id}; tabla {result.dataset_id}.",
            f"Estado: {display.status_label}. Vigencia: {result.validity}.",
            f"Motor: {result.engine_version}; método: {result.method_version}.",
            f"Fecha UTC: {result.created_at.isoformat()}",
            "Formato: " + display.format_policy,
            *methodological,
            *[
                f"Comprobación {c.name}: {c.method}; versión {c.method_version}."
                for c in result.assumptions
                if c.status != "not_checked"
            ],
            "Exportar reproduce cifras guardadas; no recalcula contrastes.",
            *[
                f"{r.kind}: {r.id}; revisión {r.revision}; SHA256 {r.hash}"
                for r in result.source_refs
            ],
        ],
    )


def report_tables(result, display):
    tables = []
    if result.technique != "descriptive_summary":
        tables.append(
            (
                "Métricas guardadas",
                ["Métrica", "Valor"],
                [
                    [
                        m.label,
                        m.formatted
                        + (f" {m.unit}" if m.unit else "")
                        + (f"; {m.reason}" if m.reason else ""),
                    ]
                    for m in display.metrics
                ],
            )
        )
    return [*tables, *[(t.title, t.columns, t.rows) for t in display.tables]]


def render_report(result, display, figures, explanations, format):
    content = list(sections(result, display, figures, explanations))
    tables = [
        (title, columns, rows) for title, columns, rows in report_tables(result, display) if rows
    ]
    if format == "txt":
        lines = ["TesisStat AI Informe de resultados", ""]
        for title, paragraphs in content[:-1]:
            lines.extend([title, *paragraphs, ""])
        for title, columns, rows in tables:
            lines.extend([title, " | ".join(columns), *[" | ".join(row) for row in rows], ""])
        for figure in figures.figures:
            lines.extend([figure.x_label + " / " + figure.y_label, figure.caption])
        lines.extend([content[-1][0], *content[-1][1]])
        return "\n".join(lines).encode("utf-8")
    if format == "pdf":
        return render_pdf(content, tables, figures)
    return render_docx(content, tables, figures)


def render_pdf(content, tables, figures):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import (
        KeepTogether,
        LongTable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        TableStyle,
    )

    out = BytesIO()
    styles = getSampleStyleSheet()
    styles["Title"].textColor = styles["Heading1"].textColor = colors.black
    styles["Title"].alignment = TA_LEFT
    styles["Heading1"].keepWithNext = True
    styles.add(
        ParagraphStyle(
            "ReportBody",
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            spaceAfter=7,
            splitLongWords=True,
        )
    )
    styles.add(
        ParagraphStyle(
            "Cell", fontName="Helvetica", fontSize=8, leading=11, spaceAfter=0, splitLongWords=True
        )
    )

    def paragraph(text, style="ReportBody"):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), styles[style])

    story = [paragraph("TesisStat AI Informe de resultados", "Title")]
    for title, paragraphs in content[:2]:
        story.append(paragraph(title, "Heading1"))
        story.extend(paragraph(p) for p in paragraphs)
    for title, columns, rows in tables:
        story.append(paragraph(title, "Heading1"))
        width = 487
        widths = (
            [width * 0.68, width * 0.32]
            if len(columns) == 2
            else [width * 0.30, *[width * 0.70 / (len(columns) - 1)] * (len(columns) - 1)]
        )
        table = LongTable(
            [[paragraph(v, "Cell") for v in row] for row in [columns, *rows]],
            colWidths=widths,
            repeatRows=1,
            hAlign="LEFT",
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5eef5")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f5f8fb")],
                    ),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d9d9d9")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.extend([table, Spacer(1, 10)])
    for n, figure in enumerate(figures.figures):
        drawing = chart_drawing(figure)
        drawing.scale(0.9, 0.9)
        drawing.width *= 0.9
        drawing.height *= 0.9
        story.append(
            KeepTogether(
                [paragraph(f"Figura {n + 1}", "Heading1"), drawing, paragraph(figure.caption)]
            )
        )
    for title, paragraphs in content[2:]:
        story.append(paragraph(title, "Heading1"))
        story.extend(paragraph(p) for p in paragraphs)
    SimpleDocTemplate(
        out,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=45,
        bottomMargin=45,
        title="Informe de resultados",
        author="TesisStat AI",
    ).build(story)
    return out.getvalue()


def render_docx(content, tables, figures):
    from docx import Document
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    document = Document()
    section = document.sections[0]
    section.top_margin = section.bottom_margin = Inches(0.7)
    section.left_margin = section.right_margin = Inches(0.8)
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
        widths = (
            [4.4, 2.1]
            if len(columns) == 2
            else [1.95, *[4.55 / (len(columns) - 1)] * (len(columns) - 1)]
        )
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
            for cell, value in zip(table.add_row().cells, row, strict=True):
                cell.text = value
        for row_index, row in enumerate(table.rows):
            row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
            for n, cell in enumerate(row.cells):
                cell.width = Inches(widths[n])
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                shade = OxmlElement("w:shd")
                shade.set(
                    qn("w:fill"),
                    "E5EEF5" if row_index == 0 else "F5F8FB" if row_index % 2 else "FFFFFF",
                )
                cell._tc.get_or_add_tcPr().append(shade)
                for p in cell.paragraphs:
                    for run in p.runs:
                        run.bold = row_index == 0
                        run.font.size = Pt(9)
        document.add_paragraph()
    for n, figure in enumerate(figures.figures):
        document.add_heading(f"Figura {n + 1}", level=2)
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.keep_with_next = True
        paragraph.add_run().add_picture(BytesIO(chart_png(figure)), width=Inches(6.5))
        document.add_paragraph(figure.caption)
    for title, paragraphs in content[2:]:
        document.add_heading(title, level=1)
        for p in paragraphs:
            document.add_paragraph(p)
    for element in (document.element, document.styles.element):
        for border in element.xpath(".//w:pBdr"):
            border.getparent().remove(border)
    out = BytesIO()
    document.save(out)
    return out.getvalue()
