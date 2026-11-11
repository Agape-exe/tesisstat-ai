"""Manual C6 revisions and mappings. Server owns IDs, references and confirmations."""

from datetime import UTC, datetime
from uuid import uuid4

from app.modules.research.context.repository import ContextError
from app.modules.research.data_workspace.service import fail, ref
from app.modules.research.sources.repository import conflict, missing
from app.shared.analysis_v2 import Confirmation, SourceRef, canonical_hash
from app.shared.instruments_v2 import (
    InstrumentContextV2,
    InstrumentMappingV2,
    InstrumentProvenanceV2,
    InstrumentStructureV2,
)


def instrument_ref(instrument):
    return SourceRef(
        kind="instrument",
        id=instrument.instrument_id,
        revision=instrument.revision,
        hash=canonical_hash(instrument),
    )


def mapping_ref(mapping):
    return SourceRef(
        kind="mapping", id=mapping.id, revision=mapping.revision, hash=canonical_hash(mapping)
    )


class InstrumentServiceV2:
    def __init__(self, workspace, contexts):
        self.workspace, self.contexts = workspace, contexts
        self.repository = workspace.repository

    def confirmation(self, revision):
        return Confirmation(
            actor_ref=self.workspace.sources.actor_ref,
            confirmed_at=datetime.now(UTC),
            revision=revision,
        )

    def raw(self, project, id_, db=None):
        self.workspace.sources.require(project)
        value = self.repository.get(project, "instrument", id_, db)
        if not value:
            missing()
        return InstrumentContextV2.model_validate(value)

    def context_ref(self, project, field):
        context = self.contexts.get(project)
        if context is None:
            fail(
                "Confirma el contexto pertinente para revisar el instrumento.", "source_stale", 409
            )
        fact = getattr(context, field)
        if not fact.confirmation or not fact.value:
            fail(
                "Confirma en Contexto la pregunta, objetivo o descripción pertinente "
                "que elegiste para este instrumento.",
                "source_stale",
                409,
            )
        return SourceRef(
            kind="context",
            id=project,
            revision=fact.confirmation.revision,
            hash=canonical_hash({"field": field, "fact": fact.model_dump(mode="json")}),
        )

    def get(self, project, id_):
        result = self.raw(project, id_)
        if result.status == "reviewed":
            try:
                if self.context_ref(project, result.context_field) != result.provenance.context_ref:
                    result.status = "stale"
            except ContextError as exc:
                if exc.status not in {404, 409, 422}:
                    raise
                result.status = "stale"
        return result

    def list(self, project):
        self.workspace.sources.require(project)
        return [
            self.get(project, v["instrument_id"])
            for v in self.repository.all(project, "instrument")
        ]

    def revisions(self, project, id_):
        self.raw(project, id_)
        return self.repository.revisions(project, "instrument", id_)

    def save(self, project, body, id_=None):
        self.workspace.sources.require(project)
        with self.repository.transaction() as db:
            old = self.raw(project, id_, db) if id_ else None
            previous = old.revision if old else 0
            if body.expected_revision != previous:
                conflict(previous)
            # Unknown client keys are temporary. Existing IDs survive edits; new IDs
            # are allocated here, even if a client submits its own UUID.
            fields = ("variables", "dimensions", "indicators", "items", "scoring_rules")
            ids = ("variable_id", "dimension_id", "indicator_id", "item_id", "scoring_rule_id")
            known = (
                {
                    str(getattr(x, key))
                    for field, key in zip(fields, ids, strict=True)
                    for x in getattr(old, field)
                }
                if old
                else set()
            )
            changes = {
                str(getattr(x, key)): str(uuid4())
                for field, key in zip(fields, ids, strict=True)
                for x in getattr(body.structure, field)
                if str(getattr(x, key)) not in known
            }
            payload = body.structure.model_dump(mode="json")

            def remap(value, key=""):
                if isinstance(value, dict):
                    return {k: remap(v, k) for k, v in value.items()}
                if isinstance(value, list):
                    return [remap(v, key) for v in value]
                return changes.get(value, value) if key in {*ids, "item_ids"} else value

            structure = InstrumentStructureV2.model_validate(remap(payload))
            for item in structure.items:
                if (item.valid_min is None) != (item.valid_max is None):
                    fail("Declara ambos límites o ninguno para cada ítem.")
            linked = {v.context_variable_id for v in structure.variables if v.context_variable_id}
            if linked:
                available = {
                    v.id
                    for d in self.workspace.datasets(project)
                    for v in self.workspace.dictionary(project, d.id).variables
                }
                if not linked.issubset(available):
                    fail("Los vínculos deben ser variables reales del diccionario del proyecto.")
            now = datetime.now(UTC)
            result = InstrumentContextV2(
                **structure.model_dump(),
                instrument_id=id_ or str(uuid4()),
                project_id=project,
                revision=previous + 1,
                created_at=old.created_at if old else now,
                updated_at=now,
                context_field=body.context_field,
            )
            self.repository.put(
                db,
                project,
                "instrument",
                result.instrument_id,
                result.model_dump(mode="json"),
                previous,
            )
        return result

    def confirm(self, project, id_, body):
        with self.repository.transaction() as db:
            old = self.raw(project, id_, db)
            if old.revision != body.expected_revision:
                conflict(old.revision)
            payload = old.model_dump(mode="json")
            payload.update(
                status="reviewed",
                revision=old.revision + 1,
                updated_at=datetime.now(UTC),
                confirmation=self.confirmation(old.revision + 1),
                provenance=InstrumentProvenanceV2(
                    context_ref=self.context_ref(project, old.context_field),
                    context_field=old.context_field,
                ),
            )
            result = InstrumentContextV2.model_validate(payload)
            self.repository.put(
                db, project, "instrument", id_, result.model_dump(mode="json"), old.revision
            )
        return result

    def mapping(self, project, id_):
        instrument = self.get(project, id_)
        payload = self.repository.get(project, "mapping", id_)
        if not payload:
            missing()
        mapping = InstrumentMappingV2.model_validate(payload)
        if mapping.status == "confirmed":
            try:
                ds, _ = self.workspace.read_table(project, mapping.dataset_ref.id)
                dictionary = self.workspace.dictionary(project, ds.id, ds)
                if (
                    instrument.status != "reviewed"
                    or mapping.instrument_ref != instrument_ref(instrument)
                    or mapping.dataset_ref != ds
                    or mapping.dictionary_ref != ref("dictionary", dictionary)
                ):
                    mapping.status = "stale"
            except ContextError as exc:
                if exc.status not in {404, 409, 422}:
                    raise
                mapping.status = "stale"
        return mapping

    def save_mapping(self, project, id_, body):
        with self.repository.transaction() as db:
            instrument = self.get(project, id_)
            if instrument.revision != body.instrument_revision:
                conflict(instrument.revision)
            old = self.repository.get(project, "mapping", id_, db)
            previous = old["revision"] if old else 0
            if body.expected_revision != previous:
                conflict(previous)
            ds, _ = self.workspace.read_table(project, body.dataset_id, body.dataset_revision)
            if any(r.kind == "instrument" and r.id == id_ for r in ds.source_refs):
                fail(
                    "Elige una fuente anterior a las puntuaciones de este instrumento; "
                    "evita un ciclo de dependencias."
                )
            dictionary = self.workspace.dictionary(project, ds.id, ds)
            items = {i.item_id for i in instrument.items}
            columns = {c.id for c in ds.columns}
            if any(m.item_id not in items or m.column_id not in columns for m in body.item_columns):
                fail("Los ítems y columnas deben pertenecer al instrumento y tabla elegidos.")
            by_column = {c: v for v in dictionary.variables for c in v.column_ids}
            for m in body.item_columns:
                variable = by_column.get(m.column_id)
                if (
                    not variable
                    or variable.identifier_confirmed.value is True
                    or (
                        variable.possible_identifier
                        and not (
                            variable.identifier_confirmed.value is False
                            and variable.identifier_confirmed.confirmation
                        )
                    )
                ):
                    fail(
                        "Un identificador no puede ser una respuesta puntuada. "
                        "Revisa su uso en Datos."
                    )
            if body.confirm and (
                instrument.status != "reviewed" or {m.item_id for m in body.item_columns} != items
            ):
                fail("Revisa el instrumento y relaciona todos sus ítems antes de confirmar.")
            result = InstrumentMappingV2(
                id=old["id"] if old else str(uuid4()),
                project_id=project,
                revision=previous + 1,
                instrument_ref=instrument_ref(instrument),
                dataset_ref=ds,
                dictionary_ref=ref("dictionary", dictionary),
                item_columns=body.item_columns,
                status="confirmed" if body.confirm else "draft",
                confirmation=self.confirmation(previous + 1) if body.confirm else None,
            )
            self.repository.put(
                db, project, "mapping", id_, result.model_dump(mode="json"), previous
            )
        return result

    def resolve(self, project, id_, rule_id):
        instrument, mapping = self.get(project, id_), self.mapping(project, id_)
        if instrument.status != "reviewed" or mapping.status != "confirmed":
            fail(
                "Revisa y confirma el instrumento y su correspondencia vigente.",
                "source_stale",
                409,
            )
        rule = next(
            (r for r in instrument.scoring_rules if str(r.scoring_rule_id) == str(rule_id)), None
        )
        if not rule:
            fail("Selecciona una regla existente y revisada del instrumento.")
        ds, rows = self.workspace.read_table(project, mapping.dataset_ref.id)
        dictionary = self.workspace.dictionary(project, ds.id, ds)
        refs = [
            *ds.source_refs,
            ref("dataset", ds),
            ref("dictionary", dictionary),
            instrument_ref(instrument),
            mapping_ref(mapping),
            instrument.provenance.context_ref,
        ]
        from app.modules.statistics.instrument_v2 import VERSION

        refs.append(
            SourceRef(
                kind="recoding",
                id=f"{id_}:{rule.scoring_rule_id}",
                revision=instrument.revision,
                hash=canonical_hash({"engine": VERSION, "rule": rule.model_dump(mode="json")}),
            )
        )
        return instrument, mapping, ds, dictionary, rows, rule, refs
