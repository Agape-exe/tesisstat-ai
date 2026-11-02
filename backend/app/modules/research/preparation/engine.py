"""Bounded, deterministic transformations; never executes file content."""

import csv
import io
import re
from decimal import Decimal, InvalidOperation
from itertools import chain

from app.modules.research.datasets.readers import (
    DatasetLimits,
    InvalidDataset,
    iter_dataset,
    read_csv,
)
from app.modules.research.eda.analyzer import ID_NAME
from app.modules.research.preparation.models import OperationSummary, Plan

RULE_VERSION = "preparation-1"


class InvalidPlan(Exception):
    pass


def _missing(value: str | None, markers: list[str], empty: bool) -> bool:
    return (
        value is None
        or (empty and not value.strip())
        or (value is not None and value.strip().casefold() in {item.casefold() for item in markers})
    )


def transform(data: bytes, format: str, plan: Plan, limits: DatasetLimits) -> dict:
    with iter_dataset(data, format, limits) as parsed:
        columns = parsed.columns.copy()
        rows = [row.copy() for row in parsed.rows]
        original_columns = columns.copy()
        original_rows = len(rows)
        warnings = parsed.warnings.copy()
        if parsed.formula_columns:
            raise InvalidPlan("El XLSX contiene fórmulas; no se exportan como datos preparados.")
    summaries = []
    for operation in plan.operations:
        kind = operation.type
        summary = OperationSummary(type=kind)
        selected = operation.columns
        if kind in {"drop_missing", "drop_columns", "trim"}:
            if (
                not selected
                or len(set(selected)) != len(selected)
                or any(name not in columns for name in selected)
            ):
                raise InvalidPlan("Selecciona columnas existentes sin repetir nombres.")
        if kind in {"replace_missing", "rename_column", "to_numeric"}:
            if operation.column not in columns:
                raise InvalidPlan("La columna indicada no existe en este punto del plan.")
        if kind == "drop_duplicates":
            seen = set()
            kept = []
            for row in rows:
                key = tuple(row)
                if key in seen:
                    summary.rows_removed += 1
                else:
                    seen.add(key)
                    kept.append(row)
            rows = kept
        elif kind == "drop_missing":
            indexes = [columns.index(name) for name in selected]
            kept = [
                row
                for row in rows
                if not any(
                    _missing(row[index], operation.missing_markers, operation.empty_is_missing)
                    for index in indexes
                )
            ]
            summary.rows_removed = len(rows) - len(kept)
            if rows and summary.rows_removed / len(rows) >= 0.3:
                warnings.append("La eliminación de faltantes afecta al menos al 30 % de las filas.")
            rows = kept
        elif kind == "replace_missing":
            if operation.value is None:
                raise InvalidPlan("Indica un valor constante de reemplazo.")
            index = columns.index(operation.column)
            for row in rows:
                if _missing(row[index], operation.missing_markers, operation.empty_is_missing):
                    if row[index] != operation.value:
                        row[index] = operation.value
                        summary.cells_changed += 1
        elif kind == "drop_columns":
            if len(selected) >= len(columns):
                raise InvalidPlan("No se pueden eliminar todas las columnas.")
            if any(ID_NAME.search(name) for name in selected):
                warnings.append("Se eliminará una columna que parece identificador.")
            indexes = [i for i, name in enumerate(columns) if name not in selected]
            summary.columns_removed = selected.copy()
            columns = [columns[i] for i in indexes]
            rows = [[row[i] for i in indexes] for row in rows]
        elif kind == "rename_column":
            name = (operation.new_name or "").strip()
            if not name or (name in columns and name != operation.column):
                raise InvalidPlan("El nuevo nombre está vacío o ya existe.")
            columns[columns.index(operation.column)] = name
            summary.rename = {operation.column: name}
        elif kind == "trim":
            indexes = [columns.index(name) for name in selected]
            for row in rows:
                for index in indexes:
                    if row[index] is not None and row[index] != row[index].strip():
                        row[index] = row[index].strip()
                        summary.cells_changed += 1
        elif kind == "to_numeric":
            index = columns.index(operation.column)
            for row in rows:
                value = row[index]
                if _missing(value, operation.missing_markers, operation.empty_is_missing):
                    continue
                try:
                    if not re.fullmatch(
                        r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value.strip()
                    ):
                        raise InvalidOperation
                    number = Decimal(value.strip())
                    if not number.is_finite():
                        raise InvalidOperation
                    canonical = f"{number:f}"
                except (InvalidOperation, ValueError) as exc:
                    raise InvalidPlan("La columna contiene valores no numéricos o fechas.") from exc
                if canonical != value:
                    if re.fullmatch(r"[+-]?0\d+(?:\.\d*)?", value.strip()):
                        warnings.append(
                            "La conversión numérica cambia representaciones con ceros iniciales."
                        )
                    row[index] = canonical
                    summary.cells_changed += 1
        summaries.append(summary)
    if any(
        value is not None
        and (
            value.lstrip().startswith(("=", "+", "@"))
            or (
                value.lstrip().startswith("-")
                and not re.fullmatch(r"-\d+(?:\.\d+)?", value.strip())
            )
        )
        for row in chain([columns], rows)
        for value in row
    ):
        raise InvalidPlan(
            "El resultado contiene valores que podrían ejecutarse como fórmulas al abrir CSV."
        )
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(columns)
    writer.writerows(rows)
    encoded = output.getvalue().encode("utf-8")
    if len(encoded) > limits.max_bytes:
        raise InvalidDataset("El resultado supera el límite de 10 MiB.")
    try:
        verified = read_csv(encoded, limits)
    except InvalidDataset as exc:
        raise InvalidPlan("El resultado no puede releerse como CSV válido.") from exc
    if verified.columns != columns or verified.row_count != len(rows):
        raise InvalidPlan("El resultado CSV no conserva la estructura prevista.")
    return {
        "columns": columns,
        "rows": rows,
        "data": encoded,
        "original_columns": original_columns,
        "original_rows": original_rows,
        "warnings": list(dict.fromkeys(warnings)),
        "operations": summaries,
        "rows_removed": original_rows - len(rows),
        "cells_changed": sum(item.cells_changed for item in summaries),
    }
