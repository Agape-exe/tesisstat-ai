"""Typed inputs used to connect selected dataset columns to the engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalysisInput:
    """Selected columns for one plan, supplied by a trusted composition layer."""

    left: tuple[Any, ...] = ()
    right: tuple[Any, ...] = ()
    groups: tuple[tuple[Any, ...], ...] = ()
    labels: tuple[str, ...] = ()
    matrix: tuple[tuple[Any, ...], ...] = ()
    predictors: tuple[tuple[Any, ...], ...] = ()
    outcome: tuple[Any, ...] = ()
    group: tuple[Any, ...] = ()
    covariate: tuple[Any, ...] = ()
