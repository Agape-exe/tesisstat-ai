"""Adapters for the controlled Research → Statistics dataset boundary."""

from __future__ import annotations

from collections.abc import Callable

from app.shared.contracts import DatasetReference

from .datasets import DatasetReadLimits, DatasetTable, read_dataset_bytes


class BytesDatasetReader:
    """Turn an injected, authorized byte loader into a ``DatasetReader``.

    The callable is supplied by the composition layer.  It may close over the
    authenticated project and Research ``DatasetService``; Statistics itself
    never resolves ``DatasetReference.location`` or opens arbitrary paths.
    """

    def __init__(
        self,
        read_bytes: Callable[[DatasetReference], bytes],
        limits: DatasetReadLimits | None = None,
    ) -> None:
        self._read_bytes = read_bytes
        self._limits = limits

    def read(self, reference: DatasetReference) -> DatasetTable:
        return read_dataset_bytes(reference, self._read_bytes(reference), self._limits)
