"""Pure recoding and scoring. Preview never invokes reliability."""

import math
from dataclasses import dataclass

from app.modules.statistics.inferential import StatisticalCalculationError
from app.modules.statistics.scoring import ItemScoringSpec, ScoringValidationError, _recode_value
from app.shared.instruments_v2 import ScoreCountsV2

VERSION = "instrument-scoring-v2.0.0"


class ReliabilityNotCalculable(StatisticalCalculationError):
    """A scientific/numerical precondition, distinct from unexpected engine failure."""


@dataclass
class RecodedItems:
    rows: list
    states: list
    scores: list
    counts: ScoreCountsV2
    explanations: list


def recode(instrument, mapping, dataset, dictionary, rows, rule):
    """Only the rule's items participate; all input row positions survive."""
    columns = {c.id: c for c in dataset.columns}
    links = {m.item_id: columns[m.column_id] for m in mapping.item_columns}
    items = {i.item_id: i for i in instrument.items}
    variables = {c: v for v in dictionary.variables for c in v.column_ids}
    matrix, states, scores, explanations = [], [], [], []
    missing = unknown = outside = valid = 0
    for index, row in enumerate(rows):
        values, statuses = [], []
        for id_ in rule.item_ids:
            item, column = items[id_], links[id_]
            value = row[column.position]
            markers = variables[column.id].missing_markers if column.id in variables else []
            status = "valid"
            if (
                value is None
                or not str(value).strip()
                or str(value).strip().casefold() in {m.strip().casefold() for m in markers}
            ):
                score, status = None, "missing"
            else:
                spec = ItemScoringSpec(
                    item_id=str(id_),
                    column_name=column.name,
                    response_type=item.response_type,
                    response_options=tuple(
                        (o.code, o.numeric_value) for o in item.response_options
                    ),
                    valid_min=item.valid_min,
                    valid_max=item.valid_max,
                    reverse_scored=item.reverse_scored,
                    reverse_rule=item.reverse_rule,
                )
                try:
                    score = _recode_value(spec, value, index)
                    if not math.isfinite(score):
                        raise ScoringValidationError(
                            index, str(id_), "valor fuera del rango numérico"
                        )
                except ScoringValidationError as exc:
                    score = None
                    status = "out_of_range" if "rango" in str(exc) else "unknown"
                    if len(explanations) < 20:
                        explanation = (
                            "respuesta fuera de rango"
                            if status == "out_of_range"
                            else "código o respuesta desconocida"
                        )
                        explanations.append(f"Fila {index + 1}, {item.text}: {explanation}.")
            values.append(score)
            statuses.append(status)
        matrix.append(values)
        states.append(statuses)
        missing += "missing" in statuses
        unknown += "unknown" in statuses
        outside += "out_of_range" in statuses
        if all(s == "valid" for s in statuses):
            try:
                value = math.fsum(values)
                if rule.aggregation == "mean":
                    value /= len(values)
                if not math.isfinite(value):
                    raise ValueError("La puntuación excede la precisión numérica admitida.")
            except OverflowError as exc:
                raise ValueError("La puntuación excede la precisión numérica admitida.") from exc
            scores.append(value)
            valid += 1
        else:
            scores.append(None)
    return RecodedItems(
        matrix,
        states,
        scores,
        ScoreCountsV2(
            total=len(rows),
            valid=valid,
            missing=missing,
            unknown=unknown,
            out_of_range=outside,
        ),
        explanations,
    )


def alpha_conditions(rows, item_count=None):
    """Check calculability without computing alpha, including during proposal."""
    complete = [r for r in rows if all(v is not None for v in r)]
    width = item_count if item_count is not None else len(rows[0]) if rows else 0
    if width < 2:
        return "Se requieren al menos dos ítems pertinentes."
    if len(complete) < 2:
        return "Se requieren al menos dos casos completos."
    try:
        totals = [math.fsum(r) for r in complete]
        if len(set(totals)) < 2:
            return "La puntuación total no tiene variación utilizable."
        # Check variances without evaluating alpha; the final coefficient belongs
        # exclusively to the approved C5 execution.
        vectors = list(zip(*complete, strict=True)) + [totals]
        for vector in vectors:
            center = math.fsum(vector) / len(vector)
            variance = math.fsum((v - center) ** 2 for v in vector) / (len(vector) - 1)
            if not math.isfinite(variance):
                return "La variación excede la precisión numérica admitida."
        # Numerical limits are checked by the verified motor at execution.
    except (OverflowError, ValueError):
        return "Los valores exceden la precisión numérica admitida."
    return None
