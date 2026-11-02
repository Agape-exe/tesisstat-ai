"""Use cases that combine a controlled dataset reader with descriptive stats."""

from __future__ import annotations

from collections.abc import Sequence

from app.shared.contracts import DatasetReference

from .descriptive import DescriptiveResult, describe_column
from .ports import DatasetReader


def describe_dataset(
    reference: DatasetReference,
    reader: DatasetReader,
    columns: Sequence[str] | None = None,
) -> list[DescriptiveResult]:
    """Describe selected columns from a validated Research dataset."""

    table = reader.read(reference)
    selected = list(columns) if columns is not None else list(table.columns)
    if not selected:
        raise ValueError("Debe seleccionarse al menos una columna.")
    unknown = sorted(set(selected) - set(table.columns))
    if unknown:
        raise ValueError(f"Columnas desconocidas: {', '.join(unknown)}")
    positions = {name: index for index, name in enumerate(table.columns)}
    return [
        describe_column(name, [row[positions[name]] for row in table.rows]) for name in selected
    ]
