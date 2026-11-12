"""Bounded whole-workbook inventory and deterministic rectangular extraction.

Formula source text and deterministic calculation audit are retained; cache is ignored.
All rows are read before publication. Preview is only a view of that same extraction.
"""

import hashlib
import io
import json
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from xml.etree.ElementTree import fromstring

from openpyxl import load_workbook
from openpyxl.utils.cell import get_column_letter, range_boundaries
from openpyxl.utils.exceptions import InvalidFileException

from app.modules.research.context.repository import ContextError
from app.modules.research.datasets.readers import (
    DatasetLimits,
    InvalidDataset,
    _cell,
    _headers,
    iter_dataset,
)
from app.modules.research.sources.formulas import ERROR_MESSAGES, VERSION, Calculator, ExcelTable


@dataclass(frozen=True)
class WorkbookLimits:
    max_sheets: int = 30
    max_rows: int = 150000
    max_cells: int = 2000000
    max_materialized_bytes: int = 30 * 1024 * 1024


@dataclass
class RawSheet:
    name: str
    visibility: str
    rows: list[list[str | None]]
    formula_cells: set[tuple[int, int]] = field(default_factory=set)
    merged_ranges: list[str] = field(default_factory=list)
    explanation: str | None = None
    cell_types: dict[tuple[int, int], str] = field(default_factory=dict)
    formula_results: dict[tuple[int, int], dict] = field(default_factory=dict)
    is_excel: bool = False
    unsupported_formula_cells: set[tuple[int, int]] = field(default_factory=set)

    @property
    def width(self):
        return max((len(row) for row in self.rows), default=0)


@dataclass
class Extracted:
    columns: list[str]
    rows: list[list[str | None]]
    range: str
    header_row: int
    warnings: list[str]
    source_columns: list[str] = field(default_factory=list)
    omitted_columns: list[str] = field(default_factory=list)
    calculation: dict | None = None

    @property
    def data(self) -> bytes:
        payload = {"columns": self.columns, "rows": self.rows}
        if self.calculation is not None:
            payload["calculation"] = self.calculation
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


def limit(message: str):
    raise ContextError("limit_exceeded", message, 413)


def inventory(data: bytes, format: str, limits: DatasetLimits, book: WorkbookLimits):
    if not data:
        raise ContextError("invalid_payload", "El archivo está vacío.")
    if len(data) > limits.max_bytes:
        limit("El archivo supera el límite de 10 MiB.")
    if format == "csv":
        try:
            with iter_dataset(data, "csv", limits) as parsed:
                rows = [list(parsed.columns)]
                cells = len(parsed.columns)
                for row in parsed.rows:
                    cells += len(row)
                    if cells > book.max_cells or len(rows) > book.max_rows:
                        limit("El archivo supera los límites globales de filas/celdas.")
                    rows.append(row)
            return [RawSheet("Tabla CSV", "visible", rows)]
        except InvalidDataset as exc:
            code = "limit_exceeded" if "límite" in str(exc) else "invalid_payload"
            raise ContextError(code, str(exc), 413 if code == "limit_exceeded" else 422) from exc
    if not data.startswith(b"PK\x03\x04"):
        raise ContextError("invalid_payload", "El XLSX es inválido o está cifrado.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if (
                len(entries) > limits.max_zip_entries
                or sum(e.file_size for e in entries) > limits.max_zip_bytes
            ):
                limit("El XLSX supera 50 MiB descomprimidos o 1000 entradas ZIP.")
            if any(e.flag_bits & 1 for e in entries):
                raise ContextError("invalid_payload", "No se admiten libros cifrados.")
            if any("vbaproject" in e.filename.lower() for e in entries):
                raise ContextError("unsupported_format", "No se admiten libros con macros.", 415)
        workbook = load_workbook(
            io.BytesIO(data), read_only=True, data_only=False, keep_links=False
        )
        try:
            if not workbook.sheetnames:
                raise ContextError("invalid_payload", "El XLSX no contiene hojas.")
            if len(workbook.sheetnames) > book.max_sheets:
                limit(f"El libro supera el límite de {book.max_sheets} hojas.")
            result = []
            tables = {}
            total_rows = total_cells = 0
            for name in workbook.sheetnames:
                sheet = workbook[name]
                if not hasattr(sheet, "iter_rows"):
                    result.append(
                        RawSheet(
                            sheet.title,
                            sheet.sheet_state,
                            [],
                            explanation=(
                                "Hoja de gráfico, sin observaciones tabulares. Puedes excluirla."
                            ),
                        )
                    )
                    continue
                # Do not trust worksheet dimension metadata to hide trailing observations.
                sheet.reset_dimensions()
                raw = RawSheet(sheet.title, sheet.sheet_state, [], is_excel=True)
                xml = fromstring(workbook._archive.read(sheet._worksheet_path))
                namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
                raw.merged_ranges = [
                    merged.attrib["ref"]
                    for merged in xml.findall(f"{namespace}mergeCells/{namespace}mergeCell")
                ]
                # Table metadata is read from this ZIP only; relationships never fetch URLs.
                for part in xml.findall(f"{namespace}tableParts/{namespace}tablePart"):
                    rel_id = part.attrib.get(
                        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                    )
                    # Read-only sheets need internal relationship resolution for table metadata.
                    path = sheet._worksheet_path
                    rel_path = posixpath.join(
                        posixpath.dirname(path), "_rels", posixpath.basename(path) + ".rels"
                    )
                    if rel_path not in workbook._archive.namelist():
                        continue
                    relations = fromstring(workbook._archive.read(rel_path))
                    rel = next((r for r in relations if r.attrib.get("Id") == rel_id), None)
                    if rel is None or rel.attrib.get("TargetMode") == "External":
                        continue
                    target = rel.attrib.get("Target", "")
                    target = (
                        target.lstrip("/")
                        if target.startswith("/")
                        else posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
                    )
                    if (
                        not target.startswith("xl/tables/")
                        or target not in workbook._archive.namelist()
                    ):
                        continue
                    table = fromstring(workbook._archive.read(target))
                    columns = [
                        c.attrib["name"]
                        for c in table.findall(f"{namespace}tableColumns/{namespace}tableColumn")
                    ]
                    if (
                        table.attrib.get("headerRowCount", "1") == "1"
                        and table.attrib.get("totalsRowCount", "0") == "0"
                    ):
                        tables[table.attrib["displayName"]] = ExcelTable(
                            raw.name, table.attrib["ref"], columns
                        )
                del xml
                for row_number, cells in enumerate(sheet.iter_rows(), 1):
                    total_rows += 1
                    total_cells += len(cells)
                    if row_number > limits.max_rows + 1 or len(cells) > limits.max_columns:
                        limit("Una hoja supera 50 000 filas de datos o 200 columnas.")
                    if total_rows > book.max_rows or total_cells > book.max_cells:
                        limit("El libro supera 150 000 filas físicas o 2 000 000 celdas.")
                    values = []
                    for column, cell in enumerate(cells, 1):
                        value = cell.value
                        if cell.data_type == "f" and not isinstance(value, str):
                            raw.unsupported_formula_cells.add((row_number, column))
                            # Array/data-table objects must never leak repr memory addresses
                            # into immutable content or be mistaken for scalar expressions.
                            value = getattr(value, "text", None) or json.dumps(
                                dict(value), sort_keys=True, ensure_ascii=False
                            )
                        values.append(_cell(value))
                        if cell.value is not None:
                            raw.cell_types[(row_number, column)] = (
                                "formula"
                                if cell.data_type == "f"
                                else "error"
                                if cell.data_type == "e"
                                else "boolean"
                                if cell.data_type == "b"
                                else "date"
                                if cell.is_date
                                else "number"
                                if cell.data_type == "n"
                                else "text"
                            )
                        if cell.data_type == "f":
                            raw.formula_cells.add((row_number, column))
                    while values and values[-1] is None:
                        values.pop()
                    raw.rows.append(values)
                while raw.rows and not raw.rows[-1]:
                    raw.rows.pop()
                result.append(raw)
            Calculator(result, tables).resolve()
            return result
        finally:
            workbook.close()
    except ContextError:
        raise
    except (
        zipfile.BadZipFile,
        OSError,
        ValueError,
        KeyError,
        SyntaxError,
        IndexError,
        InvalidFileException,
    ) as exc:
        raise ContextError(
            "invalid_payload", "El XLSX no tiene una estructura válida o está cifrado."
        ) from exc


def extract(raw: RawSheet, header_row: int, rectangle: str, limits: DatasetLimits) -> Extracted:
    if not re.fullmatch(r"[A-Z]+[1-9][0-9]*:[A-Z]+[1-9][0-9]*", rectangle):
        raise ContextError("invalid_payload", "Usa un rango rectangular como A3:D20.")
    try:
        left, top, right, bottom = range_boundaries(rectangle)
    except ValueError as exc:
        raise ContextError("invalid_payload", "El rango no es válido.") from exc
    if (
        top != header_row
        or right < left
        or bottom < top
        or bottom > len(raw.rows)
        or right > raw.width
    ):
        raise ContextError(
            "invalid_payload", "El rango debe empezar en el encabezado y estar dentro de la hoja."
        )
    if bottom - top > limits.max_rows or right - left + 1 > limits.max_columns:
        limit("La tabla supera los límites de filas o columnas.")
    if any(r == top and left <= c <= right for r, c in raw.formula_cells):
        raise ContextError("invalid_payload", "El encabezado no puede contener fórmulas.")

    def slice_row(number):
        values = raw.rows[number - 1]
        return [values[i] if i < len(values) else None for i in range(left - 1, right)]

    selected = [
        c
        for c in range(left, right + 1)
        if any(
            raw.rows[r - 1][c - 1] not in (None, "")
            for r in range(top, bottom + 1)
            if c <= len(raw.rows[r - 1])
        )
    ]
    omitted = [get_column_letter(c) for c in range(left, right + 1) if c not in selected]
    headers = slice_row(header_row)
    if any(headers[c - left] in (None, "") or not headers[c - left].strip() for c in selected):
        raise ContextError(
            "invalid_payload",
            "Hay columnas con datos sin encabezado. Aclara el encabezado en el original "
            "y reimporta el libro completo; no se descartan esas columnas.",
        )
    try:
        columns = _headers([headers[c - left] for c in selected], limits)
    except InvalidDataset as exc:
        raise ContextError("invalid_payload", str(exc)) from exc
    if any(len(c) > 200 for c in columns):
        raise ContextError("invalid_payload", "Las cabeceras admiten hasta 200 caracteres.")
    rows = [
        [values[c - left] for c in selected]
        for values in (slice_row(number) for number in range(top + 1, bottom + 1))
    ]
    if not rows:
        raise ContextError("invalid_payload", "El rango no contiene filas de datos.")
    warnings = []
    if omitted:
        warnings.append(
            "Columnas completamente vacías omitidas: "
            + ", ".join(omitted)
            + ". Se conservan las coordenadas originales."
        )
    for merged in raw.merged_ranges:
        m_left, m_top, m_right, m_bottom = range_boundaries(merged)
        if max(left, m_left) <= min(right, m_right) and max(top, m_top) <= min(bottom, m_bottom):
            warnings.append(
                "El rango incluye celdas combinadas: se conserva solo su valor almacenado, "
                "sin rellenar las celdas vacías."
            )
            break
    if any(top < r <= bottom and left <= c <= right for r, c in raw.formula_cells):
        warnings.append(
            "Las fórmulas se recalculan con excel-subset-1, sin caché. "
            "Consulta su procedencia y errores antes de analizar."
        )
    if any(all(v in (None, "") for v in row) for row in rows):
        warnings.append("El rango confirmado incluye filas vacías; se conservan sin imputar.")
    calculation = None
    if raw.is_excel:
        formulas = [
            result
            for (r, c), result in sorted(raw.formula_results.items())
            if top < r <= bottom and c in selected
        ]
        for result in formulas:
            if result["error"]:
                warnings.append(
                    f"{result['coordinate']}: fórmula sin valor fiable ({result['error']}): "
                    f"{ERROR_MESSAGES[result['error']]}. "
                    "Corrige el original y reimporta."
                )
        if any(
            top < r <= bottom and c in selected and kind == "error"
            for (r, c), kind in raw.cell_types.items()
        ):
            warnings.append(
                "Hay errores de Excel en las celdas de origen, sin valor fiable. "
                "Se conservan como errores; corrige el original y reimporta."
            )
        calculation = {
            "engine_version": VERSION,
            "cache_policy": "ignored",
            "formulas": formulas,
            "cell_types": [
                [raw.cell_types.get((r, c), "blank") for c in selected]
                for r in range(top + 1, bottom + 1)
            ],
        }
    return Extracted(
        columns,
        rows,
        rectangle,
        header_row,
        warnings,
        [get_column_letter(c) for c in selected],
        omitted,
        calculation,
    )


def detect(raw: RawSheet, limits: DatasetLimits) -> tuple[Extracted | None, str]:
    if raw.explanation:
        return None, raw.explanation
    if raw.merged_ranges:
        return None, "La hoja contiene celdas combinadas. Confirma un rango tabular o exclúyela."
    if not raw.rows or not raw.width:
        return None, "Hoja vacía. Puedes excluirla; el original se conserva."
    if any(word in raw.name.casefold() for word in ("instruccion", "instrucción", "resumen")):
        return None, "Posible hoja de instrucciones o resumen. Confirma un rango o exclúyela."
    rectangle = f"A1:{get_column_letter(raw.width)}{len(raw.rows)}"
    try:
        table = extract(raw, 1, rectangle, limits)
        if len(table.columns) < 2 or any(
            all(v in (None, "") for v in row) or row == table.columns for row in table.rows
        ):
            return None, "Estructura ambigua o bloques separados. Confirma encabezado y rango."
        # Numeric-only cells are data, not an unambiguous header.
        if any(re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", name) for name in table.columns):
            return None, "La primera fila parece contener datos. Confirma el encabezado y rango."
        return table, "Tabla reconocida automáticamente. El contexto sigue siendo opcional."
    except ContextError as exc:
        return None, exc.message + " Confirma la fila y el rango tabular completo."
