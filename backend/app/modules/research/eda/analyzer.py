"""Deterministic, read-only exploratory profile of a complete validated dataset."""

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol

from app.modules.research.datasets.readers import DatasetLimits, iter_dataset

RULE_VERSION = "eda-1"
DATE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?$")
DATE_AMBIGUOUS = re.compile(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$")
ID_NAME = re.compile(r"(^id$|(^|_)(id|codigo|code|uuid|dni)(_|$))", re.I)


@dataclass(frozen=True)
class ProfilePolicy:
    missing_markers: frozenset[str] = frozenset({"na", "n/a", "null", "none"})
    high_missing_pct: float = 30.0
    numeric_majority_pct: float = 80.0
    top_categories: int = 10

    def __post_init__(self) -> None:
        if not (0 <= self.high_missing_pct <= 100):
            raise ValueError("El umbral de faltantes debe estar entre 0 y 100.")
        if not (0 < self.numeric_majority_pct <= 100):
            raise ValueError("El umbral numérico debe estar entre 0 y 100.")
        if not (1 <= self.top_categories <= 20):
            raise ValueError("El límite de categorías debe estar entre 1 y 20.")


def missing(value: str | None, policy: ProfilePolicy) -> bool:
    return value is None or value.strip().casefold() in policy.missing_markers | {""}


def numeric(value: str) -> Decimal | None:
    try:
        result = Decimal(value.strip())
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def iso_date(value: str) -> str | None:
    if not DATE_ISO.fullmatch(value.strip()):
        return None
    try:
        return (
            datetime.fromisoformat(value.strip()).isoformat()
            if "T" in value or " " in value
            else date.fromisoformat(value.strip()).isoformat()
        )
    except ValueError:
        return None


class Analyzer(Protocol):
    @property
    def version(self) -> str: ...

    def analyze(self, data: bytes, format: str, limits: DatasetLimits) -> dict: ...


class ExploratoryAnalyzer:
    def __init__(self, policy: ProfilePolicy | None = None) -> None:
        self.policy = policy or ProfilePolicy()

    @property
    def version(self) -> str:
        policy = self.policy
        markers = ",".join(sorted(policy.missing_markers))
        return (
            f"{RULE_VERSION}:{markers}:{policy.high_missing_pct}:"
            f"{policy.numeric_majority_pct}:{policy.top_categories}"
        )

    def analyze(self, data: bytes, format: str, limits: DatasetLimits) -> dict:
        policy = self.policy
        with iter_dataset(data, format, limits) as parsed:
            stats = [
                {
                    "values": Counter(),
                    "missing": 0,
                    "numeric": 0,
                    "date_count": 0,
                    "date_min": None,
                    "date_max": None,
                    "ambiguous": 0,
                    "spaced": 0,
                    "min": None,
                    "max": None,
                }
                for _ in parsed.columns
            ]
            seen_rows: set[tuple[str | None, ...]] = set()
            rows = duplicates = 0
            for row in parsed.rows:
                rows += 1
                key = tuple(row)
                if key in seen_rows:
                    duplicates += 1
                else:
                    seen_rows.add(key)
                for index, value in enumerate(row):
                    stat = stats[index]
                    if missing(value, policy):
                        stat["missing"] += 1
                        continue
                    assert value is not None
                    stat["values"][value] += 1
                    if value != value.strip():
                        stat["spaced"] += 1
                    number = numeric(value)
                    if number is not None:
                        stat["numeric"] += 1
                        stat["min"] = number if stat["min"] is None else min(stat["min"], number)
                        stat["max"] = number if stat["max"] is None else max(stat["max"], number)
                    parsed_date = iso_date(value)
                    if parsed_date is not None:
                        stat["date_count"] += 1
                        stat["date_min"] = (
                            parsed_date
                            if stat["date_min"] is None
                            else min(stat["date_min"], parsed_date)
                        )
                        stat["date_max"] = (
                            parsed_date
                            if stat["date_max"] is None
                            else max(stat["date_max"], parsed_date)
                        )
                    elif DATE_AMBIGUOUS.fullmatch(value.strip()):
                        stat["ambiguous"] += 1
            profiles = []
            missing_total = 0
            problem_count = 0
            warnings = (
                [
                    {
                        "severity": "quality",
                        "message": (
                            "Se identificaron registros completamente duplicados; "
                            "pueden ser observaciones legítimas."
                        ),
                    }
                ]
                if duplicates
                else []
            )
            for index, (name, stat) in enumerate(zip(parsed.columns, stats, strict=True)):
                present = rows - stat["missing"]
                distinct = len(stat["values"])
                missing_pct = 100 * stat["missing"] / rows if rows else 0
                numeric_count = stat["numeric"]
                date_count = stat["date_count"]
                identifier = bool(ID_NAME.search(name)) or (
                    rows >= 3
                    and present == rows
                    and distinct == rows
                    and all(len(value) >= 6 for value in stat["values"])
                )
                if present == 0:
                    kind = "vacío"
                elif index in parsed.formula_columns:
                    kind = "desconocido"
                elif numeric_count == present and not identifier:
                    kind = "numérico" if distinct > min(10, max(1, present // 2)) else "categórico"
                elif date_count == present and not stat["ambiguous"]:
                    kind = "temporal"
                elif numeric_count and numeric_count < present:
                    kind = "mixto"
                elif stat["ambiguous"] or date_count:
                    kind = "mixto"
                elif distinct <= min(20, max(1, present // 2)):
                    kind = "categórico"
                else:
                    kind = "texto"
                issues = []

                def warn(
                    severity: str,
                    message: str,
                    column_name: str = name,
                    column_issues: list = issues,
                ) -> None:
                    item = {"severity": severity, "message": f"La columna {column_name} {message}"}
                    column_issues.append(item)
                    warnings.append(item)

                if present == 0:
                    warn("blocking", "está completamente vacía.")
                elif distinct == 1:
                    warn("quality", "contiene un único valor observado.")
                if missing_pct >= policy.high_missing_pct and present:
                    warn("quality", "tiene un porcentaje elevado de valores faltantes.")
                if numeric_count and numeric_count < present:
                    if 100 * numeric_count / present >= policy.numeric_majority_pct:
                        warn("quality", "es mayormente numérica y contiene valores incompatibles.")
                    else:
                        warn("quality", "mezcla valores numéricos y no numéricos.")
                if stat["ambiguous"]:
                    warn("quality", "contiene fechas de formato ambiguo.")
                if stat["spaced"]:
                    warn("info", "contiene valores con espacios iniciales o finales.")
                if identifier:
                    warn(
                        "info",
                        "parece ser un identificador; revisa su significado "
                        "antes de tratarla como cuantitativa.",
                    )
                if index in parsed.formula_columns:
                    warn("quality", "contiene fórmulas XLSX no calculadas.")
                if any(item["severity"] in {"quality", "blocking"} for item in issues):
                    problem_count += 1
                frequencies = (
                    [
                        {
                            "value": value[:120],
                            "count": count,
                            "percentage": 100 * count / present if present else 0,
                        }
                        for value, count in sorted(
                            stat["values"].items(), key=lambda item: (-item[1], item[0])
                        )[: policy.top_categories]
                    ]
                    if kind == "categórico"
                    else []
                )
                incompatible = (
                    [value[:120] for value in stat["values"] if numeric(value) is None][:5]
                    if numeric_count
                    else []
                )
                profiles.append(
                    {
                        "name": name,
                        "suggested_type": kind,
                        "records": rows,
                        "present": present,
                        "missing": stat["missing"],
                        "missing_percentage": missing_pct,
                        "distinct": distinct,
                        "uniqueness_percentage": 100 * distinct / present if present else 0,
                        "constant": present > 0 and distinct == 1,
                        "possible_identifier": identifier,
                        "numeric_valid": numeric_count,
                        "numeric_min": str(stat["min"])
                        if stat["min"] is not None and numeric_count == present
                        else None,
                        "numeric_max": str(stat["max"])
                        if stat["max"] is not None and numeric_count == present
                        else None,
                        "incompatible_examples": incompatible,
                        "date_min": stat["date_min"] if present and date_count == present else None,
                        "date_max": stat["date_max"] if present and date_count == present else None,
                        "frequencies": frequencies,
                        "warnings": issues,
                    }
                )
                missing_total += stat["missing"]
            for warning in parsed.warnings:
                warnings.append({"severity": "quality", "message": warning})
            return {
                "rule_version": self.version,
                "summary": {
                    "rows": rows,
                    "columns": len(parsed.columns),
                    "cells": rows * len(parsed.columns),
                    "missing": missing_total,
                    "missing_percentage": 100 * missing_total / (rows * len(parsed.columns))
                    if rows
                    else 0,
                    "duplicates": duplicates,
                    "duplicate_percentage": 100 * duplicates / rows if rows else 0,
                    "constant_columns": sum(profile["constant"] for profile in profiles),
                    "empty_columns": sum(profile["present"] == 0 for profile in profiles),
                    "problem_columns": problem_count,
                },
                "columns": profiles,
                "warnings": warnings,
            }
