"""Safe scalar projection of local detection; no rows, categories or IDs go to the model."""

from app.modules.conversation.guided_service import guidance
from app.modules.conversation.tutor_privacy import (
    identifier_positions,
    project_text,
    table_private_terms,
)
from app.modules.research.data_workspace.service import ref
from app.shared.analysis_v2 import SourceRef


def table_summary(workspace, project, selection, dataset, rows, dictionary, selected_ids):
    local = guidance(workspace, project, selection, table=(dataset, rows, dictionary))
    denied = table_private_terms(dataset, rows, dictionary)
    evidence, data = [], []

    def add(kind, text, source, variable=None, context_field=None):
        key = f"f{len(evidence)}"
        evidence.append(
            {
                "key": key,
                "kind": kind,
                "text": text,
                "source_ref": source,
                "variable": variable,
                "context_field": context_field,
            }
        )
        return key

    source = ref("dataset", dataset)
    add(
        "calculated",
        f"La tabla seleccionada contiene {dataset.row_count} registros y "
        f"{len(dataset.columns)} columnas, según el servidor.",
        source,
    )
    by_id = {v["variable_id"]: v for v in local["variables"]}
    variables = [v for v in dictionary.variables if not selected_ids or v.id in selected_ids]
    for n, variable in enumerate(variables[:30]):
        detection = by_id.get(variable.id)
        if not detection:
            continue
        column = next(c for c in dataset.columns if c.id == variable.column_ids[0])
        identifier = detection["possible_identifier"] or column.position in identifier_positions(
            dataset, dictionary
        )
        alias = f"Variable {n + 1}"
        projected_name = project_text(column.name, private_terms=denied)
        name = alias if identifier or projected_name["omitted"] else projected_name["text"]
        scale_confirmed = bool(variable.measurement_scale.confirmation)
        scale = variable.measurement_scale.value if scale_confirmed else "unknown"
        key = add(
            "detected",
            f"El encabezado «{name}» corresponde a formato "
            f"{detection['detected_type']} detectado localmente; "
            + (
                "se trata como posible identificador y se excluye del análisis."
                if identifier
                else "su formato no confirma significado ni escala."
            ),
            source,
            alias,
        )
        data.append(
            {
                "variable": alias,
                "variable_id": variable.id,
                "name": name,
                "detected_type": detection["detected_type"],
                "scale": scale,
                "scale_confirmed": scale_confirmed,
                "identifier": identifier,
                "meaning_confirmed": bool(variable.description.confirmation),
                "missing": detection["missing"],
                "formula_errors": detection["formula_errors"],
                "constant": detection["constant"],
                "evidence_key": key,
            }
        )
        if identifier:
            continue
        declared = []
        if variable.name.confirmation and variable.name.value != column.name:
            declared.append(
                "nombre: " + project_text(variable.name.value, private_terms=denied)["text"]
            )
        if variable.description.confirmation and variable.description.value:
            declared.append(
                "significado: "
                + project_text(variable.description.value, private_terms=denied)["text"]
            )
        if scale_confirmed:
            declared.append(f"escala: {scale}")
        if declared:
            add(
                "confirmed",
                f"Para «{name}», has confirmado " + "; ".join(declared) + ".",
                ref("dictionary", dictionary),
                alias,
            )
        if detection["missing"] or detection["formula_errors"] or detection["constant"]:
            add(
                "calculated",
                f"La comprobación local de «{name}» cuenta "
                f"{detection['missing']} faltantes y {detection['formula_errors']} "
                "errores de fórmula; no es un resultado inferencial."
                + (
                    " Entre los valores presentes no hay variación."
                    if detection["constant"]
                    else ""
                ),
                source,
                alias,
            )
    data.insert(
        0, {"rows": dataset.row_count, "columns": len(dataset.columns), "kind": dataset.kind}
    )
    if dataset.kind == "imported":
        table_context = workspace.sources.context(project, dataset.id)
        if table_context.revision:
            for field, label in (
                ("row_meaning", "Cada fila representa"),
                ("purpose", "Finalidad de la tabla"),
            ):
                fact = getattr(table_context, field)
                if fact.confirmation and fact.value:
                    add(
                        "confirmed",
                        "Según tu declaración confirmada, "
                        + label.lower()
                        + ": "
                        + project_text(fact.value, private_terms=denied)["text"]
                        + ".",
                        SourceRef(
                            kind="table_context",
                            id=dataset.id,
                            revision=table_context.revision,
                            hash=table_context.hash,
                        ),
                        context_field=f"/table/{field}",
                    )
    return data, evidence
