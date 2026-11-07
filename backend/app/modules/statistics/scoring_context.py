"""Pure conversion from a confirmed InstrumentContext to scoring specifications.

This module consumes only the contract DTO. It does not read Research
repositories, invoke InstrumentContextReader, persist a result, or expose HTTP.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.shared.instrument_context import InstrumentContext, ScoringRule

from .scoring import (
    ItemScoringSpec,
    ReliabilityComputation,
    ScoringComputation,
    ScoringRuleSpec,
    calculate_cronbach_reliability,
    calculate_scores,
)


class InstrumentContextConsumptionError(ValueError):
    """Raised when a context is not eligible for statistical scoring."""


@dataclass(frozen=True)
class ContextScoringInputs:
    """Pure scoring inputs derived from one confirmed rule in a contract DTO."""

    item_specs: tuple[ItemScoringSpec, ...]
    rule: ScoringRuleSpec


def _require_confirmed_mapping(context: InstrumentContext) -> None:
    mapping = context.dataset_mapping
    if context.status != "reviewed":
        raise InstrumentContextConsumptionError("El instrumento debe estar revisado.")
    if context.confirmation.state != "confirmed":
        raise InstrumentContextConsumptionError("El instrumento requiere confirmación humana.")
    if mapping is None:
        raise InstrumentContextConsumptionError("El instrumento no tiene un mapeo de dataset.")
    if mapping.status != "confirmed" or mapping.confirmation.state != "confirmed":
        raise InstrumentContextConsumptionError("El mapeo de dataset debe estar confirmado.")
    if mapping.instrument_version != context.version:
        raise InstrumentContextConsumptionError(
            "El mapeo no corresponde a esta versión del instrumento."
        )


def scoring_inputs_from_context(
    context: InstrumentContext, scoring_rule_id: str
) -> ContextScoringInputs:
    """Build pure scoring specs from a reviewed, fully confirmed context."""

    _require_confirmed_mapping(context)
    rule = next(
        (
            candidate
            for candidate in context.scoring_rules
            if str(candidate.scoring_rule_id) == scoring_rule_id
        ),
        None,
    )
    if rule is None:
        raise InstrumentContextConsumptionError("No se encontró la regla de puntuación.")
    if not rule.confirmed:
        raise InstrumentContextConsumptionError("La regla de puntuación debe estar confirmada.")
    return ContextScoringInputs(
        item_specs=_item_specs(context, rule),
        rule=ScoringRuleSpec(
            rule_id=str(rule.scoring_rule_id),
            item_ids=tuple(str(item_id) for item_id in rule.item_ids),
            aggregation=rule.aggregation,
            missing_policy=rule.missing_policy,
        ),
    )


def _item_specs(context: InstrumentContext, rule: ScoringRule) -> tuple[ItemScoringSpec, ...]:
    assert context.dataset_mapping is not None
    columns = {
        mapping.item_id: mapping.column_name for mapping in context.dataset_mapping.item_columns
    }
    items = {item.item_id: item for item in context.items}
    return tuple(
        ItemScoringSpec(
            item_id=str(item_id),
            column_name=columns[item_id],
            response_type=items[item_id].response_type,
            response_options=tuple(
                (option.code, option.numeric_value) for option in items[item_id].response_options
            ),
            valid_min=items[item_id].valid_min,
            valid_max=items[item_id].valid_max,
            reverse_scored=items[item_id].reverse_scored,
            reverse_rule=items[item_id].reverse_rule,
        )
        for item_id in rule.item_ids
    )


def calculate_context_scores(
    context: InstrumentContext,
    scoring_rule_id: str,
    rows: Sequence[Mapping[str, object]],
) -> ScoringComputation:
    """Score synthetic or authorized rows through a contract-only boundary."""

    inputs = scoring_inputs_from_context(context, scoring_rule_id)
    return calculate_scores(rows, inputs.item_specs, inputs.rule)


def calculate_context_cronbach(
    context: InstrumentContext,
    scoring_rule_id: str,
    rows: Sequence[Mapping[str, object]],
) -> ReliabilityComputation:
    """Calculate alpha from the rule's original recoded items, never aggregate scores."""

    inputs = scoring_inputs_from_context(context, scoring_rule_id)
    return calculate_cronbach_reliability(rows, inputs.item_specs)
