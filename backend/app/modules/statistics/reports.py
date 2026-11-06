"""Deterministic report renderers for completed statistical analyses.

The module deliberately keeps rendering separate from calculation.  DOCX uses
the already-approved ``python-docx`` dependency and PDF is a small, dependency-
free text report suitable for the development/demo flow.
"""

from __future__ import annotations

from collections.abc import Sequence
from textwrap import wrap

from app.shared.contracts import AnalysisResult

_BOUNDED_EFFECTS = frozenset(
    {
        "r",
        "rho",
        "r_squared",
        "eta_squared",
        "omega_squared",
        "cramers_v",
        "rank_biserial_effect",
        "rank_effect",
        "epsilon_squared",
    }
)


def _bar(value: float, *, minimum: float, maximum: float, width: int = 20) -> str:
    """Render a deterministic ASCII marker on a documented numeric scale."""

    bounded = max(minimum, min(maximum, value))
    position = round((bounded - minimum) / (maximum - minimum) * (width - 1))
    return "[" + "".join("*" if index == position else "-" for index in range(width)) + "]"


def _figure_lines(result: AnalysisResult) -> tuple[str, ...]:
    """Build a figure from persisted metrics only; never read dataset observations."""

    effects = [metric for metric in result.metrics if metric.name in _BOUNDED_EFFECTS]
    p_values = [
        metric
        for metric in result.metrics
        if metric.name in {"p_value", "model_p_value"} and 0 <= metric.value <= 1
    ]
    if not effects and not p_values:
        return ()
    lines = ["Figura 1. Resumen gráfico de métricas persistidas"]
    if effects:
        lines.append("Asociaciones y efectos (escala -1 a 1)")
        lines.extend(
            f"- {metric.name}: {_bar(metric.value, minimum=-1, maximum=1)} {metric.value:.6g}"
            for metric in effects
        )
    if p_values:
        lines.append("P-valores (escala 0 a 1; referencia alfa=0.05)")
        lines.extend(
            f"- {metric.name}: {_bar(metric.value, minimum=0, maximum=1)} {metric.value:.6g}"
            for metric in p_values
        )
    lines.append("Nota: referencia visual; no determina significancia automáticamente.")
    return tuple(lines)


def authorized_scatter_figure(
    x_label: str,
    y_label: str,
    points: Sequence[tuple[float, float]],
    *,
    complete_pair_count: int,
    sampled: bool,
) -> tuple[str, ...]:
    """Render a compact, deterministic scatter figure from authorized pairs.

    The caller is responsible for obtaining these values through the scoped
    authorization flow. Rendering deliberately receives only released pairs,
    never a dataset reference or an arbitrary query expression.
    """

    if not points:
        return ()
    width, height = 31, 11
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    minimum_x, maximum_x = min(xs), max(xs)
    minimum_y, maximum_y = min(ys), max(ys)
    span_x = maximum_x - minimum_x or 1.0
    span_y = maximum_y - minimum_y or 1.0
    grid = [[" " for _ in range(width)] for _ in range(height)]
    for x, y in points:
        column = min(width - 1, max(0, round((x - minimum_x) / span_x * (width - 1))))
        row = min(height - 1, max(0, round((maximum_y - y) / span_y * (height - 1))))
        grid[row][column] = "x"
    shown = len(points)
    return (
        f"Dispersión autorizada: {x_label} y {y_label}",
        *["|" + "".join(row) + "|" for row in grid],
        "+" + "-" * width + "+",
        f"Eje X: {x_label} ({minimum_x:.6g} a {maximum_x:.6g})",
        f"Eje Y: {y_label} ({minimum_y:.6g} a {maximum_y:.6g})",
        (
            f"{complete_pair_count} pares completos; se representan {shown} "
            "pares mediante posiciones agrupadas."
        ),
        (
            "Muestra determinista limitada a la respuesta autorizada."
            if sampled
            else "Se representaron todos los pares autorizados."
        ),
        "Nota: figura descriptiva; no determina significancia automáticamente.",
    )


def authorized_residual_figure(
    outcome_label: str,
    points: Sequence[tuple[float, float]],
    *,
    complete_observation_count: int,
    sampled: bool,
) -> tuple[str, ...]:
    """Render a bounded fitted-versus-residual plot from released diagnostics.

    ``points`` must originate in the authorized residual diagnostic, so this
    renderer cannot select columns or read arbitrary dataset rows on its own.
    """

    if not points:
        return ()
    width, height = 31, 11
    fitted = [point[0] for point in points]
    residuals = [point[1] for point in points]
    minimum_x, maximum_x = min(fitted), max(fitted)
    minimum_y, maximum_y = min(min(residuals), 0.0), max(max(residuals), 0.0)
    span_x = maximum_x - minimum_x or 1.0
    span_y = maximum_y - minimum_y or 1.0
    grid = [[" " for _ in range(width)] for _ in range(height)]
    for value, residual in points:
        column = min(width - 1, max(0, round((value - minimum_x) / span_x * (width - 1))))
        row = min(height - 1, max(0, round((maximum_y - residual) / span_y * (height - 1))))
        grid[row][column] = "x"
    zero_row = min(height - 1, max(0, round(maximum_y / span_y * (height - 1))))
    for column in range(width):
        if grid[zero_row][column] == " ":
            grid[zero_row][column] = "-"
    return (
        f"Residuos autorizados frente a valores ajustados: {outcome_label}",
        *["|" + "".join(row) + "|" for row in grid],
        "+" + "-" * width + "+",
        f"Eje X: valores ajustados ({minimum_x:.6g} a {maximum_x:.6g})",
        f"Eje Y: residuos ({minimum_y:.6g} a {maximum_y:.6g}); línea horizontal = 0",
        (
            f"{complete_observation_count} observaciones completas; se representan "
            f"{len(points)} mediante posiciones agrupadas."
        ),
        (
            "Muestra determinista limitada a la respuesta autorizada."
            if sampled
            else "Se representaron todas las observaciones autorizadas."
        ),
        "Nota: diagnóstico descriptivo; no determina significancia automáticamente.",
    )


def authorized_group_figure(
    group_label: str,
    outcome_label: str,
    points: Sequence[tuple[str, float]],
    *,
    complete_observation_count: int,
    sampled: bool,
) -> tuple[str, ...]:
    """Render a compact distribution summary from authorized group outcomes only."""

    if not points:
        return ()
    grouped: dict[str, list[float]] = {}
    for label, value in points:
        grouped.setdefault(label, []).append(value)
    minimum = min(value for _, value in points)
    maximum = max(value for _, value in points)
    span = maximum - minimum or 1.0
    width = 25

    def marker(value: float) -> int:
        return min(width - 1, max(0, round((value - minimum) / span * (width - 1))))

    lines = [f"Distribución autorizada de {outcome_label} por {group_label}"]
    for label, values in grouped.items():
        ordered = sorted(values)
        middle = len(ordered) // 2
        median = (ordered[(len(ordered) - 1) // 2] + ordered[middle]) / 2
        row = [" " for _ in range(width)]
        row[marker(ordered[0])] = "|"
        row[marker(ordered[-1])] = "|"
        row[marker(median)] = "*"
        lines.append(
            f"- {label}: [" + "".join(row) + f"] n={len(values)}; "
            f"mín={ordered[0]:.6g}; mediana={median:.6g}; máx={ordered[-1]:.6g}"
        )
    lines.extend(
        (
            f"Escala común de {outcome_label}: {minimum:.6g} a {maximum:.6g}; * = mediana.",
            (
                f"{complete_observation_count} observaciones completas; se representan "
                f"{len(points)} mediante resumen por grupo."
            ),
            (
                "Muestra estratificada y determinista limitada a la respuesta autorizada."
                if sampled
                else "Se representaron todas las observaciones autorizadas."
            ),
            "Nota: figura descriptiva; no determina significancia automáticamente.",
        )
    )
    return tuple(lines)


def authorized_paired_figure(
    before_label: str,
    after_label: str,
    points: Sequence[tuple[float, float]],
    *,
    complete_pair_count: int,
    sampled: bool,
) -> tuple[str, ...]:
    """Render paired changes without accepting a dataset or arbitrary columns."""

    if not points:
        return ()
    changes = [after - before for before, after in points]
    increased = sum(change > 0 for change in changes)
    decreased = sum(change < 0 for change in changes)
    unchanged = len(changes) - increased - decreased
    return (
        f"Pares autorizados: {before_label} y {after_label}",
        f"Cambios: aumentan={increased}; disminuyen={decreased}; sin cambio={unchanged}.",
        (
            f"Cambio mínimo={min(changes):.6g}; "
            f"mediana={sorted(changes)[len(changes) // 2]:.6g}; máximo={max(changes):.6g}."
        ),
        f"{complete_pair_count} pares completos; se representan {len(points)} pares.",
        "Muestra determinista limitada a la respuesta autorizada."
        if sampled
        else "Se representaron todos los pares autorizados.",
        "Nota: figura descriptiva; no determina significancia automáticamente.",
    )


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


def render_text(
    result: AnalysisResult,
    *,
    context: tuple[str, ...] = (),
    observation_figures: tuple[tuple[str, ...], ...] = (),
) -> str:
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
    figure = _figure_lines(result)
    if figure:
        lines.extend(["", *figure])
    figure_number = 2 if figure else 1
    for observation_figure in observation_figures:
        if observation_figure:
            lines.extend(
                [
                    "",
                    f"Figura {figure_number}. {observation_figure[0]}",
                    *observation_figure[1:],
                ]
            )
            figure_number += 1
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


def render_docx(
    result: AnalysisResult,
    *,
    context: tuple[str, ...] = (),
    observation_figures: tuple[tuple[str, ...], ...] = (),
) -> bytes:
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
    figure = _figure_lines(result)
    if figure:
        document.add_heading(figure[0], level=2)
        for line in figure[1:]:
            document.add_paragraph(line)
    figure_number = 2 if figure else 1
    for observation_figure in observation_figures:
        if observation_figure:
            document.add_heading(f"Figura {figure_number}. {observation_figure[0]}", level=2)
            for line in observation_figure[1:]:
                document.add_paragraph(line)
            figure_number += 1
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


def render_pdf(
    result: AnalysisResult,
    *,
    context: tuple[str, ...] = (),
    observation_figures: tuple[tuple[str, ...], ...] = (),
) -> bytes:
    """Paginated plain-text PDF. WinAnsi supports Spanish, but not full Unicode.

    Unsupported glyphs are explicitly disclosed and replaced; DOCX retains Unicode.
    Keep byte offsets exact, wrap long tokens and never truncate report content.
    """
    report = render_text(result, context=context, observation_figures=observation_figures)
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
