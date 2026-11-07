import json
from pathlib import Path
from uuid import UUID

import pytest

from app.modules.statistics.scoring import ScoringValidationError
from app.orchestration.instrument_scoring_preview import (
    InstrumentScoringPreviewService,
    ScoringPreviewRequest,
)
from app.orchestration.research_statistics import AuthorizedInstrumentData
from app.shared.instrument_contracts import InstrumentContext

ROOT = Path(__file__).resolve().parents[2]
CONTEXT = InstrumentContext.model_validate_json(
    (ROOT / "docs" / "contracts" / "examples" / "instrument_confirmed_with_mapping.json").read_text(
        encoding="utf-8"
    )
)
RULE_ID = CONTEXT.scoring_rules[0].scoring_rule_id


class FakeInstrumentBridge:
    def __init__(self, rows: tuple[dict[str, object], ...]) -> None:
        self.rows = rows
        self.calls: list[tuple[UUID, UUID, UUID]] = []

    def get_authorized_instrument_data(
        self, project_id: UUID, instrument_id: UUID, scoring_rule_id: UUID
    ) -> AuthorizedInstrumentData:
        self.calls.append((project_id, instrument_id, scoring_rule_id))
        return AuthorizedInstrumentData(
            context=CONTEXT,
            rows=self.rows,
            column_names=("p1_comunicacion_directa", "p2_info_contradictoria"),
        )


def request() -> ScoringPreviewRequest:
    return ScoringPreviewRequest(
        project_id=CONTEXT.project_id,
        instrument_id=CONTEXT.instrument_id,
        scoring_rule_id=RULE_ID,
    )


def complete_rows() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "p1_comunicacion_directa": str(value),
            "p2_info_contradictoria": str(6 - value),
        }
        for value in range(1, 6)
    )


def test_builds_deterministic_preview_without_raw_rows() -> None:
    bridge = FakeInstrumentBridge(complete_rows())
    service = InstrumentScoringPreviewService(bridge)  # type: ignore[arg-type]

    first = service.preview(request())
    second = service.preview(request())

    assert first == second
    assert first.status == "previewed"
    assert first.scores == (2.0, 4.0, 6.0, 8.0, 10.0)
    assert first.score_cases.model_dump() == {"total": 5, "valid": 5, "missing": 0}
    assert first.reliability.status == "calculated"
    assert first.reliability.alpha == 1.0
    assert len(first.fingerprint) == 64
    assert bridge.calls == [
        (CONTEXT.project_id, CONTEXT.instrument_id, RULE_ID),
        (CONTEXT.project_id, CONTEXT.instrument_id, RULE_ID),
    ]
    serialized = json.dumps(first.model_dump(mode="json"), ensure_ascii=False)
    assert "p1_comunicacion_directa" not in serialized
    assert "p2_info_contradictoria" not in serialized


def test_reports_missing_scores_and_unavailable_reliability() -> None:
    bridge = FakeInstrumentBridge(
        (
            {"p1_comunicacion_directa": "1", "p2_info_contradictoria": "5"},
            {"p1_comunicacion_directa": "2", "p2_info_contradictoria": None},
        )
    )

    preview = InstrumentScoringPreviewService(bridge).preview(request())  # type: ignore[arg-type]

    assert preview.scores == (2.0, None)
    assert preview.score_cases.model_dump() == {"total": 2, "valid": 1, "missing": 1}
    assert preview.reliability.status == "not_calculable"
    assert preview.reliability.alpha is None
    assert preview.reliability.valid_rows == 1
    assert preview.reliability.excluded_rows == 1
    assert len(preview.warnings) == 2


def test_invalid_code_rejects_preview_instead_of_returning_partial_result() -> None:
    bridge = FakeInstrumentBridge(
        ({"p1_comunicacion_directa": "99", "p2_info_contradictoria": "5"},)
    )

    with pytest.raises(ScoringValidationError, match="código de respuesta desconocido"):
        InstrumentScoringPreviewService(bridge).preview(request())  # type: ignore[arg-type]


def test_fingerprint_changes_when_derived_scores_change() -> None:
    first = InstrumentScoringPreviewService(FakeInstrumentBridge(complete_rows())).preview(  # type: ignore[arg-type]
        request()
    )
    changed_rows = list(complete_rows())
    changed_rows[-1] = {
        "p1_comunicacion_directa": "4",
        "p2_info_contradictoria": "1",
    }
    second = InstrumentScoringPreviewService(  # type: ignore[arg-type]
        FakeInstrumentBridge(tuple(changed_rows))
    ).preview(request())

    assert first.fingerprint != second.fingerprint
