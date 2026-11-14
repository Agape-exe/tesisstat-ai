"""Controlled dataset access for demo fixtures and Research references.

The Statistics module never resolves a filesystem path from user input.  The
integration boundary receives an opaque :class:`DatasetReference` and bytes
provided by an injected reader; this module validates and parses those bytes.
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from openpyxl import load_workbook

from app.shared.contracts import DatasetReference

from .descriptive import ColumnProfile, profile_column


class DatasetReadError(ValueError):
    """Raised when a referenced dataset cannot be safely parsed."""


@dataclass(frozen=True)
class DatasetReadLimits:
    """Safety limits aligned with Research's local dataset reader."""

    max_bytes: int = 10 * 1024 * 1024
    max_rows: int = 50_000
    max_columns: int = 200
    max_zip_bytes: int = 50 * 1024 * 1024
    max_zip_entries: int = 1_000


@dataclass(frozen=True)
class DatasetTable:
    """A validated tabular dataset represented without a filesystem path."""

    columns: tuple[str, ...]
    rows: tuple[tuple[str | None, ...], ...]
    format: Literal["csv", "xlsx"]
    warnings: tuple[str, ...] = ()

    @property
    def row_count(self) -> int:
        return len(self.rows)


def _headers(values: list[str | None], limits: DatasetReadLimits) -> tuple[str, ...]:
    if not values or len(values) > limits.max_columns:
        raise DatasetReadError("El dataset no tiene cabeceras o supera el límite de columnas.")
    if any(value is None or not value.strip() for value in values):
        raise DatasetReadError("Todas las columnas deben tener una cabecera.")
    names = tuple(value.strip() for value in values if value is not None)
    if len(set(names)) != len(names):
        raise DatasetReadError("Las cabeceras no pueden repetirse.")
    return names


def _cell(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _read_csv_bytes(data: bytes, limits: DatasetReadLimits) -> DatasetTable:
    try:
        content = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise DatasetReadError("El CSV debe estar codificado en UTF-8.") from error
    if not content.strip():
        raise DatasetReadError("El archivo está vacío.")

    try:
        candidates = (",", ";")
        delimiter = max(
            candidates,
            key=lambda candidate: len(
                next(csv.reader(io.StringIO(content, newline=""), delimiter=candidate, strict=True))
            ),
        )
        reader = csv.reader(io.StringIO(content, newline=""), delimiter=delimiter, strict=True)
        columns = _headers(next(reader), limits)
        rows: list[tuple[str | None, ...]] = []
        for row_number, row in enumerate(reader, start=2):
            if len(rows) >= limits.max_rows:
                raise DatasetReadError("El dataset supera el límite de filas.")
            if len(row) != len(columns):
                raise DatasetReadError(
                    f"La fila {row_number} tiene una cantidad incorrecta de campos."
                )
            rows.append(tuple(value if value != "" else None for value in row))
    except (csv.Error, StopIteration) as error:
        raise DatasetReadError("El CSV no tiene una estructura válida.") from error

    return DatasetTable(columns=columns, rows=tuple(rows), format="csv")


def _read_xlsx_bytes(data: bytes, limits: DatasetReadLimits) -> DatasetTable:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if any(entry.filename.lower().endswith("vbaproject.bin") for entry in entries):
                raise DatasetReadError("No se admiten libros con macros.")
            if (
                len(entries) > limits.max_zip_entries
                or sum(entry.file_size for entry in entries) > limits.max_zip_bytes
            ):
                raise DatasetReadError("El XLSX supera el límite de contenido descomprimido.")
            if any(entry.flag_bits & 1 for entry in entries):
                raise DatasetReadError("No se admiten XLSX cifrados.")

        workbook = load_workbook(
            io.BytesIO(data), read_only=True, data_only=False, keep_links=False
        )
        try:
            if not workbook.sheetnames:
                raise DatasetReadError("El XLSX no contiene hojas.")
            sheet = workbook[workbook.sheetnames[0]]
            if sheet.max_column > limits.max_columns:
                raise DatasetReadError("El dataset supera el límite de columnas.")
            if sheet.max_row > limits.max_rows + 1:
                raise DatasetReadError("El dataset supera el límite de filas.")

            iterator = sheet.iter_rows(
                max_row=limits.max_rows + 2, max_col=sheet.max_column, values_only=False
            )
            header = next(iterator)
            columns = _headers([_cell(cell.value) for cell in header], limits)
            rows: list[tuple[str | None, ...]] = []
            formulas = any(cell.data_type == "f" for cell in header)
            for _row_number, cells in enumerate(iterator, start=2):
                if len(rows) >= limits.max_rows:
                    raise DatasetReadError("El dataset supera el límite de filas.")
                if len(cells) > len(columns) and any(
                    cell.value is not None for cell in cells[len(columns) :]
                ):
                    raise DatasetReadError("Hay datos fuera de las columnas declaradas.")
                formulas |= any(cell.data_type == "f" for cell in cells)
                row = tuple(_cell(cell.value) for cell in cells[: len(columns)])
                rows.append(row + (None,) * (len(columns) - len(row)))
        finally:
            workbook.close()
    except DatasetReadError:
        raise
    except (zipfile.BadZipFile, OSError, ValueError, KeyError, StopIteration) as error:
        raise DatasetReadError("El XLSX no tiene una estructura válida.") from error

    warnings = (
        ("El archivo contiene fórmulas: se muestran como texto y no se calculan.",)
        if formulas
        else ()
    )
    return DatasetTable(
        columns=columns,
        rows=tuple(rows),
        format="xlsx",
        warnings=warnings,
    )


def read_dataset_bytes(
    reference: DatasetReference,
    data: bytes,
    limits: DatasetReadLimits | None = None,
) -> DatasetTable:
    """Validate and parse bytes for an opaque Research ``DatasetReference``.

    The reference metadata is checked against the parsed table.  No value from
    ``reference.location`` is opened or interpreted as a local path.
    """

    limits = limits or DatasetReadLimits()
    if not data:
        raise DatasetReadError("El dataset está vacío.")
    if len(data) > limits.max_bytes:
        raise DatasetReadError("El dataset supera el límite de bytes.")
    if reference.format == "csv":
        table = _read_csv_bytes(data, limits)
    elif reference.format == "xlsx":
        table = _read_xlsx_bytes(data, limits)
    else:  # Defensive guard if the contract grows a new format.
        raise DatasetReadError(f"Formato no permitido: {reference.format}.")

    if tuple(reference.columns) != table.columns:
        raise DatasetReadError("Las columnas del dataset no coinciden con DatasetReference.")
    if reference.row_count != table.row_count:
        raise DatasetReadError("La cantidad de filas no coincide con DatasetReference.")
    return table


@dataclass(frozen=True)
class DatasetDefinition:
    id: str
    label: str
    path: Path


def fixture_catalog(root: Path | None = None) -> dict[str, DatasetDefinition]:
    root = root or Path(__file__).resolve().parents[4]
    fixtures = root / "fixtures" / "datasets"
    definitions = (
        DatasetDefinition("association", "Asociación (30 registros)", fixtures / "association.csv"),
        DatasetDefinition(
            "quality_issues", "Calidad de datos (casos límite)", fixtures / "quality_issues.csv"
        ),
    )
    return {definition.id: definition for definition in definitions}


def read_csv_dataset(definition: DatasetDefinition) -> dict[str, list[str | None]]:
    with definition.path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError("El CSV no contiene encabezados.")
        columns = {name: [] for name in reader.fieldnames}
        for row in reader:
            for name in columns:
                columns[name].append(row.get(name))
    return columns


def list_profiles(definition: DatasetDefinition) -> list[ColumnProfile]:
    data = read_csv_dataset(definition)
    return [profile_column(name, values) for name, values in data.items()]
