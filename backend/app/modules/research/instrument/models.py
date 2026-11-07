"""Domain models for research measurement instruments and psychometric scales.

Canonical definitions have been centralized into app.shared.instrument_contracts.
All classes, constants and functions are re-exported here to maintain backwards
compatibility with internal Research module imports.
"""

from app.shared.instrument_contracts import (
    _PII_COLUMN_PATTERN,
    DatasetMapping,
    InstrumentConfirmation,
    InstrumentDimension,
    InstrumentIndicator,
    InstrumentItem,
    InstrumentProvenance,
    InstrumentVariable,
    ItemColumnMapping,
    ResponseOption,
    ScoringRule,
    Sha256Hex,
    StrictDomainModel,
    is_pii_column,
)

__all__ = [
    "_PII_COLUMN_PATTERN",
    "DatasetMapping",
    "InstrumentConfirmation",
    "InstrumentDimension",
    "InstrumentIndicator",
    "InstrumentItem",
    "InstrumentProvenance",
    "InstrumentVariable",
    "ItemColumnMapping",
    "ResponseOption",
    "ScoringRule",
    "Sha256Hex",
    "StrictDomainModel",
    "is_pii_column",
]
