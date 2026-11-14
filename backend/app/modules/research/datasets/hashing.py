"""Dataset hashing utilities shared across Research and Orchestration."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.research.datasets.models import Dataset


def compute_dataset_hash(dataset: Dataset, raw_bytes: bytes) -> str:
    """Compute SHA-256 of serialized dataset metadata (excluding 'active') + raw bytes."""
    metadata = dataset.model_dump_json(exclude={"active"}).encode()
    return hashlib.sha256(metadata + raw_bytes).hexdigest()
