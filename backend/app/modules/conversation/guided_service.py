"""Closed, reviewed C02 action over the existing C3/C4 services and transaction."""

from app.modules.research.data_workspace.models import DictionaryPatch, ProfileRequest
from app.modules.research.data_workspace.service import fail
from app.modules.research.eda.analyzer import ProfilePolicy, iso_date, missing, numeric
from app.modules.research.intents.models import IntentChanges, IntentPatch
from app.modules.research.sources.formulas import ERROR_PREFIX
from app.shared.analysis_v2 import canonical_hash


def guidance(workspace, project, selection, *, table=None):
    """Local facts. Only the explicit safe projection in tutor_summary may leave here."""
    tables = workspace.datasets(project)
    result = {"table_count": len(tables), "selected_table": None, "variables": []}
    target_dataset_id = selection.dataset_id
    if (
        not target_dataset_id
        and tables
        and not any((selection.intent_id, selection.plan_id, selection.result_id))
    ):
        target_dataset_id = tables[0].id

    if table is None and (
        not target_dataset_id or any((selection.intent_id, selection.plan_id, selection.result_id))
    ):
        return result
    if table is None:
        dataset, rows = workspace.read_table(project, target_dataset_id)
        dictionary = workspace.dictionary(project, dataset.id, dataset)
    else:
        dataset, rows, dictionary = table
    result["selected_table"] = {
        "id": dataset.id,
        "name": dataset.name,
        "rows": dataset.row_count,
        "columns": len(dataset.columns),
        "identical_rows": len(rows) - len({tuple(row) for row in rows}),
    }
    result["warnings"] = (
        workspace.sources.table(project, dataset.id).warnings if dataset.kind == "imported" else []
    )
    for variable in dictionary.variables:
        if len(variable.column_ids) != 1:
            continue
        column = next(c for c in dataset.columns if c.id == variable.column_ids[0])
        policy = ProfilePolicy(
            missing_markers=frozenset(m.strip().casefold() for m in variable.missing_markers)
        )
        values = [r[column.position] for r in rows if not missing(r[column.position], policy)]
        errors = sum(bool(v and v.startswith(ERROR_PREFIX)) for v in values)
        numbers = bool(values) and all(numeric(v) is not None for v in values)
        known_scale = variable.measurement_scale.value
        identifier = variable.identifier_confirmed.value is True
        suggested = (
            known_scale
            if known_scale in {"nominal", "ordinal", "interval", "ratio"}
            else ("interval" if numbers else "nominal")
        )
        result["variables"].append(
            {
                "variable_id": variable.id,
                "name": variable.name.value or column.name,
                "detected_type": "numérico"
                if numbers
                else "fecha"
                if values and all(iso_date(v) for v in values)
                else "texto o mixto"
                if values
                else "vacío",
                "missing": len(rows) - len(values),
                "formula_errors": max(errors, column.formula_error_count),
                "possible_identifier": variable.possible_identifier or identifier,
                "scale_confirmed": bool(variable.measurement_scale.confirmation),
                "constant": len(set(values)) == 1,
                "suggested_scale": suggested,
                "selected": numbers
                and not errors
                and not column.formula_error_count
                and not identifier
                and not variable.possible_identifier,
            }
        )
    return result


def prepare_descriptive(tutor, project, request):
    workspace, store = tutor.analysis.workspace, tutor.store
    workspace.sources.require(project)
    signature = canonical_hash(request.model_dump(mode="json"))
    with store.transaction() as db:
        receipt = store.get(project, "guided_action", str(request.request_id), db)
        if receipt:
            if receipt["signature"] != signature:
                fail("Este intento ya pertenece a otra selección.", "revision_conflict", 409)
            # Retry recovers the same resource, never creates another analysis.
            intent = tutor.analysis.intents.get(project, receipt["intent_id"])
            return {"intent_id": intent.id, "dataset_id": intent.dataset_id, "replayed": True}
        context, _ = tutor.builder.build(project, request.selection)
        allowed = any(a.kind == request.kind for a in context.allowed_actions)
        if not allowed or context.context_fingerprint != request.context_fingerprint:
            fail(
                "La selección o sus fuentes cambiaron. Actualiza y revisa las variables.",
                "source_stale",
                409,
            )
        table_id = request.selection.dataset_id
        if not table_id:
            datasets = workspace.datasets(project)
            table_id = datasets[0].id if datasets else None
        if not table_id:
            fail("No hay una tabla seleccionada ni disponible.", "no_table", 400)
        dataset, _ = workspace.read_table(project, table_id)
        dictionary = workspace.dictionary(project, table_id, dataset, db)
        ids = [v.variable_id for v in request.variables]
        if len(set(ids)) != len(ids):
            fail("No repitas variables.")
        selected = [v for v in dictionary.variables if v.id in ids]
        if len(selected) != len(ids):
            fail("Selecciona variables de la tabla actual.")
        for variable in selected:
            if len(variable.column_ids) != 1 or variable.identifier_confirmed.value is True:
                fail("Revisa el vínculo o identificador en Datos antes de incluirlo.")
            column = next(c for c in dataset.columns if c.id == variable.column_ids[0])
            if column.formula_error_count:
                fail("Corrige y reimporta las fórmulas sin valor fiable.")
        workspace.patch_dictionary(
            project,
            table_id,
            DictionaryPatch(
                expected_revision=dictionary.revision,
                dataset_revision=dataset.revision,
                dataset_hash=dataset.hash,
                changes={
                    v.variable_id: {"measurement_scale": v.measurement_scale}
                    for v in request.variables
                },
                confirm_fields=[
                    f"/variables/{v.variable_id}/measurement_scale" for v in request.variables
                ],
            ),
            db=db,
        )
        workspace.compute_profile(
            project,
            table_id,
            ProfileRequest(
                dataset_revision=dataset.revision,
                dataset_hash=dataset.hash,
                confirm=True,
            ),
            db=db,
        )
        intent = tutor.analysis.intents.save(
            project,
            IntentPatch(
                expected_revision=0,
                confirm=True,
                changes=IntentChanges(
                    kind="descriptive",
                    estimand="summary",
                    dataset_id=table_id,
                    variable_ids=ids,
                    question="Describir "
                    + ", ".join(v.name.value or "variable" for v in selected)[:1950],
                ),
            ),
            db=db,
        )
        store.put(
            db,
            project,
            "guided_action",
            str(request.request_id),
            {
                "revision": 1,
                "signature": signature,
                "intent_id": intent.id,
                "dataset_id": table_id,
            },
            0,
        )
    return {"intent_id": intent.id, "dataset_id": table_id, "replayed": False}
