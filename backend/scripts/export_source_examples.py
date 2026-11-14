"""Reproducible C3 examples linked to actual synthetic CSV bytes."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from app.modules.research.sources.readers import Extracted
from app.shared.analysis_v2 import Confirmation, Fact, Provenance, canonical_hash
from app.shared.data_sources_v2 import (
    ExtractionV2,
    FormulaAuditV2,
    ImportedTableV2,
    SourceFileV2,
    SourceSheetV2,
    TableColumnV2,
    TableContextV2,
    TablePreviewV2,
)
from scripts.export_v2_examples import identifier

OUTPUT = Path(__file__).resolve().parents[2] / "contracts/v2/examples"
CSV = b"codigo,nota\n0001,12\n0002,\n0003,14\n"


def examples():
    now = datetime(2026, 11, 9, 12, tzinfo=UTC)
    project_id, file_id, sheet_id, table_id = [identifier(n) for n in range(101, 105)]
    extracted = Extracted(
        ["codigo", "nota"], [["0001", "12"], ["0002", ""], ["0003", "14"]], "A1:B4", 1, []
    )
    extraction = ExtractionV2(header_row=1, range=extracted.range)
    original_hash = hashlib.sha256(CSV).hexdigest()
    table = ImportedTableV2(
        id=table_id,
        project_id=project_id,
        file_id=file_id,
        sheet_id=sheet_id,
        created_at=now,
        original_hash=original_hash,
        content_hash=extracted.hash,
        extraction=extraction,
        row_count=3,
        column_count=2,
        columns=[
            TableColumnV2(id=identifier(110 + i), name=name, position=i)
            for i, name in enumerate(extracted.columns)
        ],
    )
    sheet = SourceSheetV2(
        id=sheet_id,
        project_id=project_id,
        file_id=file_id,
        index=0,
        name="Tabla CSV",
        row_count=4,
        column_count=2,
        state="ready",
        explanation="Tabla reconocida automáticamente.",
        hash="0" * 64,
        table_id=table_id,
        extraction=extraction,
    )
    sheet.hash = canonical_hash(sheet)
    source = SourceFileV2(
        id=file_id,
        project_id=project_id,
        name="data-sources.synthetic.csv",
        format="csv",
        size=len(CSV),
        hash=original_hash,
        created_at=now,
        updated_at=now,
        state="complete",
        sheets=[sheet],
    )
    context = TableContextV2(
        project_id=project_id,
        table_id=table_id,
        revision=1,
        updated_at=now,
        hash="0" * 64,
        name=Fact(
            value="Notas sintéticas",
            provenance=Provenance(kind="manual"),
            confirmation=Confirmation(actor_ref="local", confirmed_at=now, revision=1),
        ),
    )
    context.hash = canonical_hash(context)
    preview = TablePreviewV2(table=table, rows=extracted.rows)
    audit = FormulaAuditV2(
        engine_version="excel-subset-1",
        formulas=[
            {
                "coordinate": "D2",
                "formula": "=AVERAGE(B2:C2)",
                "value": "3.0",
                "status": "calculated",
                "error": None,
                "dependencies": ["'Mediciones'!B2", "'Mediciones'!C2"],
            }
        ],
        cell_types=[["text", "number", "number", "formula"]],
    )
    return {
        type(model).__name__: model.model_dump(mode="json")
        for model in (source, sheet, table, context, preview, audit)
    }


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, payload in examples().items():
        (OUTPUT / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    (OUTPUT / "data-sources.synthetic.csv").write_bytes(CSV)


if __name__ == "__main__":
    main()
