"""Bounded CSV/XLSX parsing; only UTF-8 (with optional BOM) is accepted."""

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import date, datetime

from openpyxl import load_workbook

from app.modules.research.datasets.models import DatasetPreview


class InvalidDataset(Exception):
    pass


@dataclass(frozen=True)
class DatasetLimits:
    max_bytes: int = 10 * 1024 * 1024
    max_rows: int = 50000
    max_columns: int = 200
    preview_rows: int = 20
    max_zip_bytes: int = 50 * 1024 * 1024
    max_zip_entries: int = 1000


def _headers(values: list[str | None], limits: DatasetLimits) -> list[str]:
    if not values or len(values) > limits.max_columns:
        raise InvalidDataset("El archivo no tiene cabeceras o supera el límite de columnas.")
    if any(value is None or not value.strip() for value in values):
        raise InvalidDataset("Todas las columnas deben tener una cabecera.")
    names = [value.strip() for value in values if value is not None]
    if len(set(names)) != len(names):
        raise InvalidDataset("Las cabeceras no pueden repetirse.")
    return names


def read_csv(data: bytes, limits: DatasetLimits) -> DatasetPreview:
    try:
        content = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidDataset("El CSV debe estar codificado en UTF-8.") from exc
    if not content.strip():
        raise InvalidDataset("El archivo está vacío.")
    try:
        delimiter = max(
            (",", ";"),
            key=lambda candidate: len(
                next(csv.reader(io.StringIO(content, newline=""), delimiter=candidate, strict=True))
            ),
        )
        reader = csv.reader(io.StringIO(content, newline=""), delimiter=delimiter, strict=True)
        columns = _headers(next(reader), limits)
        rows: list[list[str | None]] = []
        count = 0
        for row in reader:
            count += 1
            if count > limits.max_rows:
                raise InvalidDataset("El dataset supera el límite de filas.")
            if len(row) != len(columns):
                raise InvalidDataset(
                    f"La fila {count + 1} tiene una cantidad incorrecta de campos."
                )
            if len(rows) < limits.preview_rows:
                rows.append(row)
    except (csv.Error, StopIteration) as exc:
        raise InvalidDataset("El CSV no tiene una estructura válida.") from exc
    return DatasetPreview(
        columns=columns,
        rows=rows,
        row_count=count,
        column_count=len(columns),
        format="csv",
        warnings=[],
    )


def _cell(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def read_xlsx(data: bytes, limits: DatasetLimits) -> DatasetPreview:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if any(entry.filename.lower().endswith("vbaproject.bin") for entry in entries):
                raise InvalidDataset("No se admiten libros con macros.")
            if (
                len(entries) > limits.max_zip_entries
                or sum(entry.file_size for entry in entries) > limits.max_zip_bytes
            ):
                raise InvalidDataset("El XLSX supera el límite de contenido descomprimido.")
            if any(entry.flag_bits & 1 for entry in entries):
                raise InvalidDataset("No se admiten XLSX cifrados.")
        workbook = load_workbook(
            io.BytesIO(data), read_only=True, data_only=False, keep_links=False
        )
        try:
            if not workbook.sheetnames:
                raise InvalidDataset("El XLSX no contiene hojas.")
            sheet = workbook[workbook.sheetnames[0]]
            if sheet.max_column > limits.max_columns:
                raise InvalidDataset("El dataset supera el límite de columnas.")
            if sheet.max_row > limits.max_rows + 1:
                raise InvalidDataset("El dataset supera el límite de filas.")
            iterator = sheet.iter_rows(
                max_row=limits.max_rows + 2, max_col=sheet.max_column, values_only=False
            )
            header = next(iterator)
            columns = _headers([_cell(cell.value) for cell in header], limits)
            rows: list[list[str | None]] = []
            count = 0
            formulas = any(cell.data_type == "f" for cell in header)
            for cells in iterator:
                count += 1
                if count > limits.max_rows:
                    raise InvalidDataset("El dataset supera el límite de filas.")
                if len(cells) > len(columns) and any(
                    cell.value is not None for cell in cells[len(columns) :]
                ):
                    raise InvalidDataset("Hay datos fuera de las columnas declaradas.")
                formulas |= any(cell.data_type == "f" for cell in cells)
                if len(rows) < limits.preview_rows:
                    rows.append(
                        [_cell(cell.value) for cell in cells[: len(columns)]]
                        + [None] * max(0, len(columns) - len(cells))
                    )
            warnings = (
                ["El archivo contiene fórmulas: se muestran como texto y no se calculan."]
                if formulas
                else []
            )
            return DatasetPreview(
                columns=columns,
                rows=rows,
                row_count=count,
                column_count=len(columns),
                format="xlsx",
                sheet=sheet.title,
                warnings=warnings,
            )
        finally:
            workbook.close()
    except (zipfile.BadZipFile, OSError, ValueError, KeyError, StopIteration) as exc:
        raise InvalidDataset("El XLSX no tiene una estructura válida.") from exc
