"""Generate synthetic contract examples only; never seed application storage.

C4 sources are fixture manifests, not operational C3 resources or executed analyses.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from app.shared.analysis_v2 import (
    AnalysisIntentV2,
    AnalysisSnapshotV2,
    Confirmation,
    Fact,
    ProjectContextV2,
    Provenance,
    SnapshotVariableV2,
    SourceRef,
    canonical_hash,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "contracts/v2/examples"


def identifier(n: int) -> str:
    return f"{n:08d}-0000-4000-8000-000000000000"


def examples() -> dict:
    now = datetime(2026, 11, 9, 12, tzinfo=UTC)
    confirmation = Confirmation(actor_ref="local", confirmed_at=now, revision=1)
    objective = Fact[str](
        value="Describir los importes de ventas sintéticas",
        provenance=Provenance(kind="manual"),
        confirmation=confirmation,
    )
    context = ProjectContextV2(
        project_id=identifier(1),
        revision=1,
        updated_at=now,
        state="partial",
        main_objective=objective,
    )
    intent = AnalysisIntentV2(
        id=identifier(2),
        project_id=identifier(1),
        revision=1,
        created_at=now,
        updated_at=now,
        kind="descriptive",
        estimand="summary",
        variable_ids=[identifier(3)],
        question=objective,
        confirmation=confirmation,
    )
    variable = SnapshotVariableV2(
        id=identifier(3),
        column_ids=[identifier(4)],
        name=Fact(value="Importe", provenance=Provenance(kind="manual"), confirmation=confirmation),
        measurement_scale=Fact(
            value="ratio", provenance=Provenance(kind="manual"), confirmation=confirmation
        ),
    )
    sources = {
        "dataset": {
            "id": identifier(5),
            "project_id": identifier(1),
            "revision": 1,
            "fixture": "sales.synthetic.csv",
            "columns": [{"id": identifier(4), "name": "importe"}],
            "row_count": 3,
            "synthetic": True,
        },
        "dictionary": {
            "id": identifier(6),
            "project_id": identifier(1),
            "revision": 1,
            "dataset_id": identifier(5),
            "variables": [variable.model_dump(mode="json")],
        },
        "profile": {
            "id": identifier(7),
            "project_id": identifier(1),
            "revision": 1,
            "dataset_id": identifier(5),
            "total_rows": 3,
            "valid_count": 3,
            "missing_count": 0,
            "algorithm_version": "synthetic-fixture-v1",
        },
    }
    refs = {
        kind: SourceRef(kind=kind, id=payload["id"], revision=1, hash=canonical_hash(payload))
        for kind, payload in sources.items()
    }
    refs["context"] = SourceRef(
        kind="context", id=context.project_id, revision=1, hash=canonical_hash(context)
    )
    refs["intent"] = SourceRef(kind="intent", id=intent.id, revision=1, hash=canonical_hash(intent))
    source_refs = list(refs.values())
    snapshot = AnalysisSnapshotV2(
        id=identifier(8),
        project_id=identifier(1),
        created_at=now,
        source_refs=source_refs,
        context_ref=refs["context"],
        dataset_ref=refs["dataset"],
        dictionary_ref=refs["dictionary"],
        profile_ref=refs["profile"],
        intent_ref=refs["intent"],
        confirmed_facts={"/main_objective": objective},
        variables=[variable],
        intent=intent,
        source_fingerprint=canonical_hash([r.model_dump(mode="json") for r in source_refs]),
    )
    return {
        "ProjectContextV2": context.model_dump(mode="json"),
        "AnalysisIntentV2": intent.model_dump(mode="json"),
        "AnalysisSnapshotV2": snapshot.model_dump(mode="json"),
        "sources": sources,
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, value in examples().items():
        (OUTPUT / f"{name}.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    (OUTPUT / "sales.synthetic.csv").write_text(
        "importe\n10\n20\n30\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
