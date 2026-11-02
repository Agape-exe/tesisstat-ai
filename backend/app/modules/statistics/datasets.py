"""Bounded CSV access for the module's known synthetic demonstration datasets."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .descriptive import ColumnProfile, profile_column


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
