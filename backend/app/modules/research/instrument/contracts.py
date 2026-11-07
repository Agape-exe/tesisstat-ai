"""Canonical boundary contract for InstrumentContext v1.0.0.

Centralized in app.shared.instrument_contracts as the single canonical source
of truth for Research–Statistics interoperability.
Re-exported here for full backwards compatibility with internal Research imports.
"""

from app.shared.instrument_contracts import (
    DatasetMapping,
    InstrumentConfirmation,
    InstrumentContext,
    InstrumentDimension,
    InstrumentIndicator,
    InstrumentItem,
    InstrumentProvenance,
    InstrumentVariable,
    ItemColumnMapping,
    ResponseOption,
    ScoringRule,
    StrictDomainModel,
)

__all__ = [
    "DatasetMapping",
    "InstrumentConfirmation",
    "InstrumentContext",
    "InstrumentDimension",
    "InstrumentIndicator",
    "InstrumentItem",
    "InstrumentProvenance",
    "InstrumentVariable",
    "ItemColumnMapping",
    "ResponseOption",
    "ScoringRule",
    "StrictDomainModel",
]
