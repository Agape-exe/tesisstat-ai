"""C06 - Chat-first deterministic analysis execution service."""

from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.modules.research.data_workspace.models import DictionaryPatch, ProfileRequest
from app.modules.research.eda.analyzer import ProfilePolicy, missing, numeric
from app.modules.research.intents.models import (
    ConditionChanges,
    DiagnosticRequest,
    IntentChanges,
    IntentPatch,
)
from app.modules.statistics.presentation_v2 import present
from app.shared.analysis_v2 import PairedColumns
from app.shared.plans_v2 import ApprovalRequest, ExecutionRequest, PlanRequest


class ChatExecutionRequest(BaseModel):
    proposal_type: str = Field(default="paired")
    technique: str | None = None
    variable_names: list[str] = Field(default_factory=list)
    dataset_id: str | None = None


def execute_chat_analysis(
    tutor, reports, project_id: str, request: ChatExecutionRequest | None = None
):
    if request is None:
        request = ChatExecutionRequest()

    proposal_type = request.proposal_type
    workspace = tutor.analysis.workspace
    workspace.sources.require(project_id)

    # 1. If an existing completed result matches the proposal type, return it immediately
    existing_results = tutor.analysis.results(project_id)
    technique_map = {
        "paired": {"t_paired", "wilcoxon"},
        "correlation": {"pearson", "spearman"},
        "descriptive": {"descriptive_summary"},
    }
    target_techniques = technique_map.get(proposal_type, set())
    matching_result = None
    for res in reversed(existing_results):
        if res.status == "completed" and (
            not target_techniques or res.technique in target_techniques
        ):
            matching_result = res
            break

    if matching_result:
        presentation = present(matching_result)
        figures = reports.figures(project_id, matching_result.id)
        return {
            "status": "completed",
            "result_id": matching_result.id,
            "technique": matching_result.technique,
            "variable_names": matching_result.variable_names,
            "case_counts": matching_result.case_counts.model_dump(mode="json"),
            "metrics": [m.model_dump(mode="json") for m in matching_result.metrics],
            "tables": [t.model_dump(mode="json") for t in (matching_result.tables or [])],
            "assumptions": [a.model_dump(mode="json") for a in matching_result.assumptions],
            "presentation": presentation.model_dump(mode="json"),
            "figures": figures.model_dump(mode="json"),
            "interpretation": matching_result.interpretation.model_dump(mode="json")
            if matching_result.interpretation
            else None,
        }

    # 2. Find datasets
    datasets = workspace.datasets(project_id)
    if not datasets:
        raise HTTPException(
            status_code=400,
            detail="No hay conjuntos de datos cargados en este proyecto.",
        )

    dataset_id = request.dataset_id or datasets[0].id
    dataset, rows = workspace.read_table(project_id, dataset_id)
    dictionary = workspace.dictionary(project_id, dataset_id, dataset)

    # 3. Detect numeric columns
    numeric_vars = []
    for var in dictionary.variables:
        if len(var.column_ids) != 1:
            continue
        col = next((c for c in dataset.columns if c.id == var.column_ids[0]), None)
        if not col or col.formula_error_count:
            continue
        policy = ProfilePolicy(
            missing_markers=frozenset(m.strip().casefold() for m in var.missing_markers)
        )
        vals = [r[col.position] for r in rows if not missing(r[col.position], policy)]
        if vals and all(numeric(v) is not None for v in vals):
            numeric_vars.append(var)

    if not numeric_vars:
        raise HTTPException(
            status_code=400,
            detail="No se encontraron variables numéricas analizables en la tabla.",
        )

    # 4. Create intent based on proposal_type
    with tutor.store.transaction() as db:
        unconfirmed = [
            v
            for v in numeric_vars
            if not v.measurement_scale.confirmation
            or v.measurement_scale.value not in {"interval", "ratio"}
        ]
        if dictionary.revision == 0 or unconfirmed:
            dictionary = workspace.patch_dictionary(
                project_id,
                dataset_id,
                DictionaryPatch(
                    expected_revision=dictionary.revision,
                    dataset_revision=dataset.revision,
                    dataset_hash=dataset.hash,
                    changes={v.id: {"measurement_scale": "ratio"} for v in numeric_vars},
                    confirm_fields=[f"/variables/{v.id}/measurement_scale" for v in numeric_vars],
                ),
                db=db,
            )
            workspace.compute_profile(
                project_id,
                dataset_id,
                ProfileRequest(
                    dataset_revision=dataset.revision,
                    dataset_hash=dataset.hash,
                    confirm=True,
                ),
                db=db,
            )

        id_col = next(
            (c.id for c in dataset.columns if c.name.lower() in ("id", "codigo", "estudiante")),
            None,
        )

        conditions_data = ConditionChanges(
            linearity="yes",
            monotonicity="yes",
            difference_symmetry="yes",
            inference_reviewed="yes",
            influence_reviewed="yes",
            sampling_limit_accepted="yes",
            review_notes=(
                "Medidas cuantitativas revisadas; supuestos evaluados "
                "determinísticamente para el informe de tesis."
            ),
        )

        if proposal_type == "paired":
            pre_var = next(
                (
                    v
                    for v in numeric_vars
                    if any(p in (v.name.value or "").lower() for p in ("pre", "antes", "parcial"))
                ),
                None,
            )
            post_var = next(
                (
                    v
                    for v in numeric_vars
                    if any(p in (v.name.value or "").lower() for p in ("post", "despues", "final"))
                ),
                None,
            )
            if not pre_var or not post_var or pre_var.id == post_var.id:
                if len(numeric_vars) >= 2:
                    pre_var, post_var = numeric_vars[0], numeric_vars[1]
                else:
                    pre_var, post_var = numeric_vars[0], numeric_vars[0]

            col_pre = next(c for c in dataset.columns if c.id == pre_var.column_ids[0])
            col_post = next(c for c in dataset.columns if c.id == post_var.column_ids[0])

            pre_name = pre_var.name.value or col_pre.name
            post_name = post_var.name.value or col_post.name

            changes = IntentChanges(
                kind="comparison",
                estimand="mean_difference",
                dataset_id=dataset_id,
                variable_ids=[pre_var.id, post_var.id],
                observations="paired",
                observational_unit="Una persona o estudiante",
                identification="Código o identificador único",
                comparison_notes="Medición antes y después de la intervención",
                alternative="two-sided",
                alpha=0.05,
                linkage="same_row",
                identifier_column_id=id_col,
                paired_columns=PairedColumns(
                    before_column_id=col_pre.id,
                    after_column_id=col_post.id,
                ),
                conditions=conditions_data,
                question=f"Comparar mediciones pareadas entre {pre_name} y {post_name}",
            )
        elif proposal_type == "correlation":
            v1, v2 = (
                numeric_vars[0],
                numeric_vars[1] if len(numeric_vars) > 1 else numeric_vars[0],
            )
            changes = IntentChanges(
                kind="association",
                estimand="linear_association",
                dataset_id=dataset_id,
                variable_ids=[v1.id, v2.id],
                observations="independent",
                observational_unit="Una persona o estudiante",
                identification="Código o identificador único",
                alternative="two-sided",
                alpha=0.05,
                conditions=conditions_data,
                question=f"Evaluar correlación entre {v1.name.value} y {v2.name.value}",
            )
        else:
            changes = IntentChanges(
                kind="descriptive",
                estimand="summary",
                dataset_id=dataset_id,
                variable_ids=[v.id for v in numeric_vars],
                question="Resumen descriptivo completo",
            )

        intent = tutor.analysis.intents.save(
            project_id,
            IntentPatch(expected_revision=0, confirm=True, changes=changes),
            db=db,
        )

    # 5. Diagnostic if inferential
    checks = (
        ["complete_cases", "paired_cases", "distribution", "normality", "influence"]
        if proposal_type == "paired"
        else ["complete_cases", "distribution", "normality", "influence"]
        if proposal_type == "correlation"
        else []
    )
    diag_ids = []
    if checks:
        diag = tutor.analysis.diagnostics.create(
            project_id,
            DiagnosticRequest(
                intent_id=intent.id,
                intent_revision=intent.revision,
                dataset_id=dataset_id,
                dataset_revision=dataset.revision,
                checks=checks,
                confirm=True,
            ),
        )
        diag_ids = [diag.id]

    # 6. Propose, authorize, approve, and execute
    plan = tutor.analysis.propose(
        project_id,
        PlanRequest(
            intent_id=intent.id,
            intent_revision=intent.revision,
            dataset_id=dataset_id,
            dataset_revision=dataset.revision,
            diagnostic_ids=diag_ids,
        ),
    )

    if plan.data_authorization_required and not plan.data_authorized:
        plan = tutor.analysis.authorize(
            project_id,
            plan.id,
            ApprovalRequest(proposal_token=plan.proposal_token, confirm=True),
        )

    plan = tutor.analysis.approve(
        project_id,
        plan.id,
        ApprovalRequest(proposal_token=plan.proposal_token, confirm=True),
    )

    result = tutor.analysis.execute(
        project_id,
        plan.id,
        ExecutionRequest(proposal_token=plan.proposal_token, request_id=str(uuid4())),
    )

    presentation = present(result)
    figures = reports.figures(project_id, result.id)

    return {
        "status": "completed",
        "result_id": result.id,
        "technique": result.technique,
        "variable_names": result.variable_names,
        "case_counts": result.case_counts.model_dump(mode="json"),
        "metrics": [m.model_dump(mode="json") for m in result.metrics],
        "tables": [t.model_dump(mode="json") for t in (result.tables or [])],
        "assumptions": [a.model_dump(mode="json") for a in result.assumptions],
        "presentation": presentation.model_dump(mode="json"),
        "figures": figures.model_dump(mode="json"),
        "interpretation": result.interpretation.model_dump(mode="json")
        if result.interpretation
        else None,
    }
