"""Bounded whole-workbook inventory and deterministic rectangular extraction.

Formula source text is retained, never evaluated; cached results are not substituted.
All rows are read before publication. Preview is only a view of that same extraction.
"""

import hashlib
import io
import json
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

    @property
    def data(self) -> bytes:
        return json.dumps(
            {"columns": self.columns, "rows": self.rows},
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
                raw = RawSheet(sheet.title, sheet.sheet_state, [])
                xml = fromstring(workbook._archive.read(sheet._worksheet_path))
                namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
                raw.merged_ranges = [
                    merged.attrib["ref"]
                    for merged in xml.findall(f"{namespace}mergeCells/{namespace}mergeCell")
                ]
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
                        values.append(_cell(cell.value))
                        if cell.data_type == "f":
                            raw.formula_cells.add((row_number, column))
                    while values and values[-1] is None:
                        values.pop()
                    raw.rows.append(values)
                while raw.rows and not raw.rows[-1]:
                    raw.rows.pop()
                result.append(raw)
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

    try:
        columns = _headers(slice_row(header_row), limits)
    except InvalidDataset as exc:
        raise ContextError("invalid_payload", str(exc)) from exc
    if any(len(c) > 200 for c in columns):
        raise ContextError("invalid_payload", "Las cabeceras admiten hasta 200 caracteres.")
    rows = [slice_row(number) for number in range(top + 1, bottom + 1)]
    if not rows:
        raise ContextError("invalid_payload", "El rango no contiene filas de datos.")
    warnings = []
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
            "Las fórmulas se conservan como texto; no se ejecutan ni se sustituyen por "
            "resultados almacenados en caché. No se inventan resultados."
        )
    if any(all(v in (None, "") for v in row) for row in rows):
        warnings.append("El rango confirmado incluye filas vacías; se conservan sin imputar.")
    return Extracted(columns, rows, rectangle, header_row, warnings)


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
    except ContextError:
        return None, "Encabezado o rango no inequívoco. Confirma la fila y el rango tabular."
