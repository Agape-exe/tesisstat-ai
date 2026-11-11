"""C5 read/export gate, including a second validation immediately before delivery."""

import math

from app.modules.research.context.repository import ContextError
from app.modules.statistics.diagnostics import select_cases
from app.modules.statistics.presentation_v2 import present
from app.modules.statistics.reports_v2 import render_report
from app.shared.reports_v2 import ResultFigureDataV2, ResultFiguresV2


def bounded(values, limit=500):
    if len(values) <= limit:
        return values
    return [values[round(n * (len(values) - 1) / (limit - 1))] for n in range(limit)]


class ReportsServiceV2:
    def __init__(self, analysis, tutor):
        self.analysis, self.tutor = analysis, tutor

    def guard(self, project, result_id):
        result, plan = self.analysis.result_with_plan(project, result_id)
        if (
            result.status != "completed"
            or plan.execution_status != "completed"
            or result.validity != "current"
            or plan.validity != "current"
        ):
            raise ContextError(
                "source_stale",
                "Solo se exportan o grafican resultados completados y vigentes; "
                "el histórico permanece disponible.",
                409,
            )
        if plan.status != "approved" or not plan.approval:
            raise ContextError(
                "not_approved", "La propuesta debe conservar su aprobación exacta.", 409
            )
        approval = self.analysis.store.get(project, "approval", plan.id)
        if not approval or approval.get("proposal_token") != plan.proposal_token:
            raise ContextError(
                "approval_mismatch", "La aprobación no corresponde al plan exacto.", 409
            )
        self.analysis._guard(plan, plan.proposal_token)
        with self.analysis.store.transaction() as db:
            self.analysis._authorized(plan, db)
        return result, plan

    def figures(self, project, result_id):
        result, plan = self.guard(project, result_id)
        figures, warnings = [], []
        if result.technique in {
            "pearson",
            "spearman",
            "t_paired",
            "wilcoxon",
            "t_welch",
            "t_independent",
            "mann_whitney",
        }:
            snapshot = self.analysis._snapshot(plan)
            expected = snapshot.dataset_ref
            # Scoped port checks all parents, revisions and byte hashes, never a preview.
            ds, rows = self.analysis.workspace.read_table(
                project,
                result.dataset_id,
                expected_revision=expected.revision,
                expected_hash=expected.hash,
            )
            dictionary = self.analysis.workspace.dictionary(project, ds.id, ds)
            intent = snapshot.intent
            variables = [
                next(v for v in dictionary.variables if v.id == id_) for id_ in intent.variable_ids
            ]
            if any(v.identifier_confirmed.value is True for v in variables):
                raise ContextError(
                    "invalid_payload", "Las figuras no exponen identificadores.", 409
                )
            complete, _, _ = select_cases(intent, ds, dictionary, rows)
            effective = [r for _, r in complete]
            kind, labels = "scatter", []
            x_label, y_label = result.variable_names[:2]
            if result.technique in {"t_paired", "wilcoxon"}:
                kind = "paired"
                left, right = (
                    intent.paired_columns.before_column_id,
                    intent.paired_columns.after_column_id,
                )
                columns = {c.id: c.name for c in ds.columns}
                x_label, y_label = columns[left], columns[right]
                points = [(float(r[left]), float(r[right])) for r in effective]
            elif intent.group_column_id:
                kind = "groups"
                outcome = next(v for v in variables if intent.group_column_id not in v.column_ids)
                x_label, y_label = "Grupo (orden guardado)", outcome.name.value or "Medida"
                group_labels = [g.label for g in result.case_counts.groups]
                grouped = [
                    [r for r in effective if str(r[intent.group_column_id]) == g]
                    for g in group_labels
                ]
                points, labels = [], []
                # Stratified cap: each of the two groups remains visible.
                for n, group in enumerate(grouped):
                    displayed = bounded(group, 250)
                    for r in displayed:
                        value = r[outcome.column_ids[0]]
                        if outcome.measurement_scale.value == "ordinal":
                            value = outcome.category_order.index(str(value)) + 1
                        points.append((float(n + 1), float(value)))
                        labels.append(f"Grupo {n + 1}")
                warnings.append(
                    "Los grupos se muestran por orden de aparición; "
                    "las etiquetas personales no se incluyen en la figura."
                )
            else:

                def value(row, variable):
                    raw = row[variable.column_ids[0]]
                    return (
                        float(variable.category_order.index(str(raw)) + 1)
                        if variable.measurement_scale.value == "ordinal"
                        else float(raw)
                    )

                points = [(value(r, variables[0]), value(r, variables[1])) for r in effective]
            points = bounded(points)
            if points and all(math.isfinite(v) for p in points for v in p):
                figures.append(
                    ResultFigureDataV2(
                        id=f"{result.id}-observations",
                        kind=kind,
                        x_label=x_label,
                        y_label=y_label,
                        x=[p[0] for p in points],
                        y=[p[1] for p in points],
                        labels=labels,
                        caption=f"Visualización de {len(points)} de "
                        f"{len(effective)} casos completos. "
                        "Selección determinista por posiciones; en grupos, estratificada. "
                        "No cambia el contraste ni prueba causalidad. "
                        "Pares: primera menos segunda; "
                        "rangos ordinales usan el orden confirmado.",
                        total_cases=len(effective),
                        displayed_cases=len(points),
                        policy="deterministic-complete-cases-500-v1",
                    )
                )
        # Categories and effects use persisted output; no statistical recalculation.
        for table in result.tables:
            if table.rows and all("count" in row for row in table.rows):
                rows = table.rows[:30]
                figures.append(
                    ResultFigureDataV2(
                        id=f"{table.id}-frequencies",
                        kind="bars",
                        x_label="Categorías por orden de la tabla",
                        y_label="Frecuencia de casos utilizados",
                        x=[float(n + 1) for n in range(len(rows))],
                        y=[float(r["count"]) for r in rows],
                        labels=[f"Categoría {n + 1}" for n in range(len(rows))],
                        caption="Frecuencias persistidas, con el denominador de la tabla. "
                        "Hasta treinta categorías; "
                        "consulta la tabla completa. Las etiquetas no se reproducen en la figura.",
                        total_cases=result.case_counts.used,
                        displayed_cases=result.case_counts.used,
                        policy="persisted-aggregate-v1",
                    )
                )
        for metric in result.metrics:
            suffix = metric.key.rsplit(".", 1)[-1]
            if suffix in {"mean", "median", "r", "rho", "alpha"} and metric.value is not None:
                figures.append(
                    ResultFigureDataV2(
                        id=f"{result.id}-{len(figures)}",
                        kind="metric",
                        x_label=metric.label,
                        y_label="Valor de la métrica persistida",
                        x=[1],
                        y=[metric.value],
                        source_metric_keys=[metric.key],
                        caption="Valor guardado; consulta unidades e intervalos de la tabla. "
                        "No evalúa relevancia práctica, causalidad ni validez del instrumento.",
                        total_cases=result.case_counts.used,
                        displayed_cases=result.case_counts.used,
                        policy="persisted-aggregate-v1",
                    )
                )
                if len(figures) >= 8:
                    warnings.append(
                        "Hasta ocho figuras; todas las métricas permanecen en las tablas."
                    )
                    break
        output = ResultFiguresV2(
            result_id=result.id, source_refs=result.source_refs, figures=figures, warnings=warnings
        )
        self.guard(project, result_id)
        return output

    def export(self, project, result_id, format):
        result, _ = self.guard(project, result_id)
        figures = self.figures(project, result_id)
        explanations = self.tutor.explanations(project, result_id)
        payload = render_report(result, present(result), figures, explanations, format)
        # A source, approval or authorization change during rendering prevents delivery.
        self.guard(project, result_id)
        return payload
