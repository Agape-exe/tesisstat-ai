"""C6 scoring coordinator; atomic publication via the table workspace write port."""

import hashlib
from collections import Counter
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.modules.research.data_workspace.ports import ScorePublicationPort
from app.modules.research.data_workspace.service import encoded_table, fail
from app.modules.research.instrument.v2_service import instrument_ref
from app.modules.research.sources.repository import missing
from app.modules.statistics.instrument_v2 import VERSION, recode
from app.shared.analysis_v2 import SourceRef, canonical_hash
from app.shared.data_sources_v2 import TableColumnV2
from app.shared.data_workspace_v2 import ColumnLineageV2, DatasetRefV2
from app.shared.instruments_v2 import (
    InstrumentContextV2,
    ScoreDerivedTableV2,
    ScorePreviewV2,
    ScoreRecordV2,
)


def dependencies(refs):
    """Compare all dependency identities, revisions and hashes, without ordering."""
    return Counter((r.kind, r.id, r.revision, r.hash) for r in refs)


class ScoreServiceV2:
    def __init__(self, instruments):
        self.instruments = instruments
        self.workspace = instruments.workspace
        self.publication: ScorePublicationPort = self.workspace
        self.repository = self.workspace.repository

    def resolved(self, project, id_, rule_id):
        inputs = self.instruments.resolve(project, id_, rule_id)
        try:
            computed = recode(*inputs[:5], inputs[5])
        except (ValueError, ArithmeticError):
            fail("Las reglas o valores exceden el rango numérico admitido para puntuación.")
        return inputs, computed

    def fingerprint(self, refs, rule_id, name):
        return canonical_hash(
            {
                "sources": [r.model_dump(mode="json") for r in refs],
                "rule": str(rule_id),
                "name": name,
                "engine": VERSION,
            }
        )

    def preview(self, project, id_, body):
        inputs, result = self.resolved(project, id_, body.scoring_rule_id)
        instrument, mapping, ds, _, _, rule, refs = inputs
        if (
            instrument.revision != body.expected_revision
            or mapping.revision != body.mapping_revision
        ):
            fail("Cambió el instrumento o la correspondencia.", "source_stale", 409)
        if body.column_name in {c.name for c in ds.columns}:
            fail("Ese nombre de columna ya existe. Elige otro nombre.")
        warnings = [
            "Se invierte una sola vez, antes de agregar. Faltantes y errores producen null; "
            "no se imputa ni se convierten en cero.",
            "La vista previa no calcula alfa. Solicita confiabilidad desde Análisis.",
        ]
        warnings += [
            f"Inversión: {i.text}; {i.valid_min} + {i.valid_max} − valor."
            for i in instrument.items
            if i.item_id in rule.item_ids and i.reverse_scored
        ]
        warnings.append(
            f"Se usan {len(rule.item_ids)} ítems de esta regla; "
            "los ítems ajenos no anulan su puntuación."
        )
        preview = ScorePreviewV2(
            id=str(uuid4()),
            project_id=project,
            instrument_id=id_,
            source_refs=refs,
            fingerprint=self.fingerprint(refs, rule.scoring_rule_id, body.column_name),
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            scoring_engine_version=VERSION,
            rule_id=rule.scoring_rule_id,
            counts=result.counts,
            column_name=body.column_name,
            bounded_preview=result.scores[:20],
            warnings=warnings,
            exclusions=result.explanations,
        )
        with self.repository.transaction() as db:
            *_, latest = self.instruments.resolve(project, id_, rule.scoring_rule_id)
            if latest != refs:
                fail("Las dependencias cambiaron durante la vista previa.", "source_stale", 409)
            self.repository.put(
                db, project, "score_preview", preview.id, preview.model_dump(mode="json"), 0
            )
        return preview

    def records(self, project, id_):
        self.instruments.raw(project, id_)
        result = []
        for value in self.repository.all(project, "score"):
            score = ScoreRecordV2.model_validate(value)
            if self.owner(project, score) == id_:
                result.append(score)
        return result

    def owner(self, project, score, record=None):
        """Resolve immutable publication links, never infer ownership from ancestors.

        Preview expiry only prevents a new publication; its durable metadata also
        identifies the owner of pre-existing receipts without rewriting history.
        Verify the frozen instrument revision, not its possibly edited current state.
        """
        self.workspace.sources.require(project)
        if record is None:
            payload = self.repository.get(project, "score_derived", score.derived_dataset_ref.id)
            if not payload:
                fail("Falta el linaje de la puntuación.", "storage_unavailable", 503)
            record = ScoreDerivedTableV2.model_validate(payload)
        payload = self.repository.get(project, "score_preview", record.preview_id)
        receipt = self.repository.get(project, "scored_preview", record.preview_id)
        if not payload or not receipt:
            fail("Falta la relación de publicación de la puntuación.", "storage_unavailable", 503)
        preview = ScorePreviewV2.model_validate(payload)
        owner_id = score.instrument_id if score.instrument_id is not None else preview.instrument_id
        if (
            score.project_id != project
            or record.project_id != project
            or preview.project_id != project
            or record.score_id != score.id
            or receipt["score_id"] != score.id
            or owner_id != preview.instrument_id
            or score.derived_dataset_ref != record.dataset_ref
            or score.rule_id != preview.rule_id
            or score.fingerprint != preview.fingerprint
            or score.engine_version != preview.scoring_engine_version
            or dependencies(score.source_refs) != dependencies(preview.source_refs)
            or dependencies(score.source_refs) != dependencies(record.source_refs)
        ):
            fail("La relación de publicación es inconsistente.", "storage_unavailable", 503)
        owner_refs = {
            (r.id, r.revision, r.hash)
            for r in score.source_refs
            if r.kind == "instrument" and r.id == owner_id
        }
        frozen = []
        for value in self.repository.revisions(project, "instrument", owner_id):
            candidate = InstrumentContextV2.model_validate(value)
            reference = instrument_ref(candidate)
            if (reference.id, reference.revision, reference.hash) in owner_refs:
                frozen.append(candidate)
        if (
            len(owner_refs) != 1
            or len(frozen) != 1
            or (
                frozen[0].project_id != project
                or frozen[0].status != "reviewed"
                or not any(r.scoring_rule_id == score.rule_id for r in frozen[0].scoring_rules)
            )
        ):
            fail("No se puede verificar el instrumento propietario.", "storage_unavailable", 503)
        return owner_id

    def confirm(self, project, id_, body):
        self.instruments.raw(project, id_)
        with self.repository.transaction() as db:
            request = self.repository.get(project, "score_request", str(body.request_id), db)
            if request and (
                request["preview_id"] != body.preview_id
                or request["fingerprint"] != body.fingerprint
            ):
                fail("La clave de reintento ya se usó con otra solicitud.", "request_conflict", 409)
            value = self.repository.get(project, "score_preview", body.preview_id, db)
            if not value or value["instrument_id"] != id_:
                missing()
            preview = ScorePreviewV2.model_validate(value)
            if preview.fingerprint != body.fingerprint:
                fail("La vista previa no coincide.", "source_stale", 409)
            receipt = self.repository.get(project, "scored_preview", preview.id, db)
            if receipt:
                result = ScoreRecordV2.model_validate(
                    self.repository.get(project, "score", receipt["score_id"], db)
                )
            else:
                if (
                    preview.expires_at <= datetime.now(UTC)
                    or preview.scoring_engine_version != VERSION
                ):
                    fail("La vista previa venció. Solicita una nueva.", "preview_expired", 409)
                inputs, computed = self.resolved(project, id_, preview.rule_id)
                _, _, source, _, rows, rule, refs = inputs
                if (
                    self.fingerprint(refs, rule.scoring_rule_id, preview.column_name)
                    != preview.fingerprint
                ):
                    fail(
                        "Las dependencias cambiaron; no se publicó la puntuación.",
                        "source_stale",
                        409,
                    )
                if preview.column_name in {c.name for c in source.columns}:
                    fail("Ese nombre de columna ya existe. Elige otro nombre.")
                table_id, column_id, score_id = str(uuid4()), str(uuid4()), str(uuid4())
                columns = [c.model_copy() for c in source.columns] + [
                    TableColumnV2(
                        id=column_id, name=preview.column_name, position=len(source.columns)
                    )
                ]
                output = [
                    list(row) + [str(score) if score is not None else None]
                    for row, score in zip(rows, computed.scores, strict=True)
                ]
                content = encoded_table([c.name for c in columns], output)
                if len(rows) > 50000 or len(columns) > 200 or len(content) > 10 * 1024 * 1024:
                    fail(
                        "El derivado supera los límites de tabla "
                        "(50 000 filas, 200 columnas, 10 MiB).",
                        "limit_exceeded",
                        413,
                    )
                dataset = DatasetRefV2(
                    id=table_id,
                    project_id=project,
                    hash=hashlib.sha256(content).hexdigest(),
                    kind="derived",
                    name=preview.column_name,
                    row_count=len(rows),
                    columns=columns,
                    synthetic=source.synthetic,
                    source_refs=refs,
                    preparation_ref=SourceRef(
                        kind="score", id=score_id, revision=1, hash=preview.fingerprint
                    ),
                )
                result = ScoreRecordV2(
                    id=score_id,
                    project_id=project,
                    instrument_id=id_,
                    source_refs=refs,
                    rule_id=rule.scoring_rule_id,
                    engine_version=VERSION,
                    fingerprint=preview.fingerprint,
                    derived_dataset_ref=dataset,
                    derived_column_id=column_id,
                    counts=computed.counts,
                    confirmed_by=self.workspace.sources.actor_ref,
                    confirmed_at=datetime.now(UTC),
                )
                derived = ScoreDerivedTableV2(
                    id=table_id,
                    project_id=project,
                    hash=dataset.hash,
                    dataset_ref=dataset,
                    preview_id=preview.id,
                    score_id=score_id,
                    source_table_id=source.id,
                    source_refs=refs,
                    column_lineage=[
                        ColumnLineageV2(
                            source_table_id=source.id,
                            source_column_id=c.id,
                            result_column_id=c.id,
                        )
                        for c in source.columns
                    ]
                    + [
                        ColumnLineageV2(
                            source_table_id=source.id,
                            source_column_id=m.column_id,
                            result_column_id=column_id,
                        )
                        for m in inputs[1].item_columns
                        if m.item_id in rule.item_ids
                    ],
                    row_lineage=[{source.id: n + 1} for n in range(len(rows))],
                )
                self.publication.publish_score(db, derived, content)
                self.repository.put(
                    db, project, "score", result.id, result.model_dump(mode="json"), 0
                )
                self.repository.put(
                    db,
                    project,
                    "scored_preview",
                    preview.id,
                    {"revision": 1, "score_id": result.id},
                    0,
                )
            if not request:
                self.repository.put(
                    db,
                    project,
                    "score_request",
                    str(body.request_id),
                    {
                        "revision": 1,
                        "preview_id": preview.id,
                        "fingerprint": body.fingerprint,
                        "score_id": result.id,
                    },
                    0,
                )
        return result

    def validate_derived(self, project, record):
        payload = self.repository.get(project, "score", record.score_id)
        if not payload:
            fail("Falta el recibo de puntuación.", "storage_unavailable", 503)
        score = ScoreRecordV2.model_validate(payload)
        instrument_id = self.owner(project, score, record)
        *_, refs = self.instruments.resolve(project, instrument_id, score.rule_id)
        if (
            dependencies(refs) != dependencies(record.source_refs)
            or score.engine_version != VERSION
        ):
            fail(
                "Cambió el instrumento, reglas, correspondencia o fuente del derivado.",
                "source_stale",
                409,
            )
