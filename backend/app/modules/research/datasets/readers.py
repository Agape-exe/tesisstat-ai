"""Bounded CSV/XLSX parsing shared by preview and full profiling."""

import csv
import io
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
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


@dataclass
class DatasetRows:
    columns: list[str]
    rows: Iterator[list[str | None]]
    format: str
    sheet: str | None = None
    warnings: list[str] = field(default_factory=list)
    formula_columns: set[int] = field(default_factory=set)


def _headers(values: list[str | None], limits: DatasetLimits) -> list[str]:
    if not values or len(values) > limits.max_columns:
        raise InvalidDataset("El archivo no tiene cabeceras o supera el límite de columnas.")
    if any(value is None or not value.strip() for value in values):
        raise InvalidDataset("Todas las columnas deben tener una cabecera.")
    names = [value.strip() for value in values if value is not None]
    if len(set(names)) != len(names):
        raise InvalidDataset("Las cabeceras no pueden repetirse.")
    return names


def _cell(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


@contextmanager
def iter_dataset(data: bytes, format: str, limits: DatasetLimits) -> Iterator[DatasetRows]:
    """Iterate every validated row; XLSX workbook is closed when the context exits."""
    if not data or len(data) > limits.max_bytes:
        raise InvalidDataset("El archivo está vacío o supera el límite de 10 MiB.")
    if format == "csv":
        try:
            content = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidDataset("El CSV debe estar codificado en UTF-8.") from exc
        if not content.strip() or data.startswith(b"PK\x03\x04") or b"\x00" in data:
            raise InvalidDataset("El contenido no corresponde a un CSV.")
        try:
            delimiter = max(
                (",", ";"),
                key=lambda candidate: len(
                    next(
                        csv.reader(
                            io.StringIO(content, newline=""), delimiter=candidate, strict=True
                        )
                    )
                ),
            )
            reader = csv.reader(io.StringIO(content, newline=""), delimiter=delimiter, strict=True)
            columns = _headers(next(reader), limits)

            def rows() -> Iterator[list[str | None]]:
                for count, row in enumerate(reader, 1):
                    if count > limits.max_rows:
                        raise InvalidDataset("El dataset supera el límite de filas.")
                    if len(row) != len(columns):
                        raise InvalidDataset(
                            f"La fila {count + 1} tiene una cantidad incorrecta de campos."
                        )
                    yield row

            yield DatasetRows(columns, rows(), "csv")
        except (csv.Error, StopIteration) as exc:
            raise InvalidDataset("El CSV no tiene una estructura válida.") from exc
        return
    if format != "xlsx" or not data.startswith(b"PK\x03\x04"):
        raise InvalidDataset("El contenido no corresponde a un XLSX.")
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
            result = DatasetRows(columns, iter(()), "xlsx", sheet.title)
            if any(cell.data_type == "f" for cell in header):
                result.warnings.append("El XLSX contiene fórmulas no calculadas.")

            def rows() -> Iterator[list[str | None]]:
                for count, cells in enumerate(iterator, 1):
                    if count > limits.max_rows:
                        raise InvalidDataset("El dataset supera el límite de filas.")
                    if len(cells) > len(columns) and any(
                        cell.value is not None for cell in cells[len(columns) :]
                    ):
                        raise InvalidDataset("Hay datos fuera de las columnas declaradas.")
                    formula_indices = {
                        index
                        for index, cell in enumerate(cells[: len(columns)])
                        if cell.data_type == "f"
                    }
                    result.formula_columns.update(formula_indices)
                    if formula_indices and not result.warnings:
                        result.warnings.append("El XLSX contiene fórmulas no calculadas.")
                    yield (
                        [_cell(cell.value) for cell in cells[: len(columns)]]
                        + [None] * max(0, len(columns) - len(cells))
                    )

            result.rows = rows()
            yield result
        finally:
            workbook.close()
    except (zipfile.BadZipFile, OSError, ValueError, KeyError, StopIteration, IndexError) as exc:
        raise InvalidDataset("El XLSX no tiene una estructura válida.") from exc


def _preview(data: bytes, format: str, limits: DatasetLimits) -> DatasetPreview:
    with iter_dataset(data, format, limits) as parsed:
        preview: list[list[str | None]] = []
        count = 0
        for row in parsed.rows:
            count += 1
            if len(preview) < limits.preview_rows:
                preview.append(row)
        return DatasetPreview(
            columns=parsed.columns,
            rows=preview,
            row_count=count,
            column_count=len(parsed.columns),
            format=format,
            sheet=parsed.sheet,
            warnings=parsed.warnings,
        )


def read_csv(data: bytes, limits: DatasetLimits) -> DatasetPreview:
    return _preview(data, "csv", limits)


def read_xlsx(data: bytes, limits: DatasetLimits) -> DatasetPreview:
    return _preview(data, "xlsx", limits)
