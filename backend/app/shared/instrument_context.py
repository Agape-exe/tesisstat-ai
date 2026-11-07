"""Deprecated compatibility re-exports for InstrumentContext v1.0.0.

The only canonical definition lives in ``app.shared.instrument_contracts``.
New Statistics code must import from that module and obtain the authorized
reader protocol from ``app.shared.ports``.
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
)
from app.shared.ports import InstrumentContextReader

__all__ = [
    "DatasetMapping",
    "InstrumentConfirmation",
    "InstrumentContext",
    "InstrumentContextReader",
    "InstrumentDimension",
    "InstrumentIndicator",
    "InstrumentItem",
    "InstrumentProvenance",
    "InstrumentVariable",
    "ItemColumnMapping",
    "ResponseOption",
    "ScoringRule",
]
