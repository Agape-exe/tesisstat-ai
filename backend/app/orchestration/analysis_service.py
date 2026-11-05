"""Research → planner → explicit approval → engine, local synthetic-first data."""

import hashlib
import json
import logging
import math
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.modules.research.documents.repository import DocumentRepository
from app.modules.research.documents.sqlite_repository import DocumentStorageError
from app.modules.statistics.composition import build_engine_from_research_bridge
from app.modules.statistics.engine import DeterministicStatisticalEngine
from app.modules.statistics.planner import DeterministicStatisticalPlanner, UnknownHypothesis
from app.modules.statistics.regression import linear_fitted_values
from app.modules.statistics.research_bridge import BytesDatasetReader
from app.orchestration.analysis_inputs import (
    CONNECTED,
    analysis_input,
    ancova_questions,
    categorical_association_questions,
    independent_questions,
    multiple_regression_questions,
    paired_questions,
    pearson_questions,
    reliability_questions,
    simple_regression_questions,
    spearman_questions,
)
from app.orchestration.analysis_models import (
    AnalysisRecord,
    ApprovalRequest,
    AuthorizedResidualPlot,
    AuthorizedResidualPoint,
    AuthorizedScatterPlot,
    AuthorizedScatterPoint,
    PlanRequest,
)
from app.orchestration.analysis_repository import SQLiteAnalysisRepository
from app.orchestration.data_authorization import LocalRealDataAuthorization
from app.orchestration.research_statistics import ResearchInputError, ResearchStatisticsBridge
from app.shared.contracts import AnalysisPlan, AnalysisResult, ResearchPackage

logger = logging.getLogger(__name__)


class ResearchAnalysisService:
    _MAX_SCATTER_POINTS = 2_000

    def __init__(
        self,
        bridge: ResearchStatisticsBridge,
        repository: SQLiteAnalysisRepository,
        documents: DocumentRepository,
        real_data_authorization: LocalRealDataAuthorization | None = None,
    ):
        self.bridge = bridge
        self.repository = repository
        self.documents = documents
        self.planner = DeterministicStatisticalPlanner()
        self.real_data_authorization = real_data_authorization or LocalRealDataAuthorization()

    def _version(self, project_id: UUID) -> str:
        # Public configuration includes review/configuration versions and source hashes.
        config = self.bridge.packages.configuration(project_id)
        if config.document_id is None:
            raise ResearchInputError("plan_stale", "Falta el documento metodológico confirmado.")
        try:
            # Public, project-scoped document port; no filesystem paths reach Statistics.
            document = self.documents.read(project_id, config.document_id)
        except (DocumentStorageError, FileNotFoundError, OSError) as exc:
            raise ResearchInputError(
                "document_inaccessible", "El documento metodológico ya no está disponible."
            ) from exc
        return hashlib.sha256(config.model_dump_json().encode() + document).hexdigest()

    @staticmethod
    def _token(plan: AnalysisPlan, package: ResearchPackage, version: str) -> str:
        proposal = json.dumps(plan.model_dump(exclude={"status"}), sort_keys=True)
        return hashlib.sha256((proposal + package.model_dump_json() + version).encode()).hexdigest()

    def _require_authorized_dataset(
        self, project_id: UUID, package: ResearchPackage, source_version: str
    ) -> None:
        if package.dataset.synthetic:
            return
        if not self.real_data_authorization.allows(
            project_id, package.id, package.dataset.id, source_version
        ):
            raise HTTPException(
                403,
                "Los datos no sintéticos requieren autorización explícita "
                "para este paquete vigente.",
            )

    def authorize_real_dataset(
        self, project_id: UUID, package_id: str, dataset_id: str
    ) -> tuple[str, str, str]:
        """Grant local-only access after validating the current opaque package reference."""

        package = self.bridge.get_package(project_id, package_id)
        version = self._version(project_id)
        if package.dataset.synthetic:
            raise HTTPException(409, "El dataset sintético no requiere autorización adicional.")
        if package.dataset.id != dataset_id:
            raise HTTPException(409, "El dataset no coincide con el paquete vigente.")
        self.real_data_authorization.grant(project_id, package.id, package.dataset.id, version)
        return package.id, package.dataset.id, version

    def _current(
        self, record: AnalysisRecord, *, require_authorization: bool = True
    ) -> ResearchPackage:
        if record.invalidated_at:
            raise ResearchInputError("plan_stale", record.stale_reason or "El plan está obsoleto.")
        package = self.bridge.get_package(record.project_id, record.plan.research_package_id)
        current_version = self._version(record.project_id)
        if (
            package != record.package
            or current_version != record.source_version
            or record.plan.hypothesis_id not in {item.id for item in package.hypotheses}
            or record.plan.dataset_id != package.dataset.id
            or record.proposal_token != self._token(record.plan, package, record.source_version)
        ):
            raise ResearchInputError("plan_stale", "Las fuentes o la propuesta del plan cambiaron.")
        if require_authorization:
            self._require_authorized_dataset(record.project_id, package, current_version)
        return package

    def _invalidate(self, project_id: UUID, plan_id: str, detail: str) -> None:
        with self.repository.edit(project_id, plan_id) as record:
            if record.invalidated_at is None:
                record.invalidated_at = datetime.now(UTC)
                record.stale_reason = detail
                record.approved_at = None
                if record.plan.status == "approved":
                    record.plan.status = "proposed"

    @contextmanager
    def _edit_current(self, project_id: UUID, plan_id: str):
        self.bridge.projects.get(project_id)
        try:
            with self.repository.edit(project_id, plan_id) as record:
                package = self._current(record)
                yield record, package
                self._current(record)
        except ResearchInputError as exc:
            self._invalidate(project_id, plan_id, str(exc))
            raise

    def propose(self, project_id: UUID, request: PlanRequest) -> AnalysisRecord:
        package = self.bridge.get_package(project_id, request.package_id)
        version = self._version(project_id)
        self._require_authorized_dataset(project_id, package, version)
        try:
            plan = self.planner.propose(package, request.hypothesis_id)
        except UnknownHypothesis as exc:
            raise HTTPException(404, "La hipótesis no pertenece al paquete vigente.") from exc
        if (
            plan.research_package_id != package.id
            or plan.hypothesis_id != request.hypothesis_id
            or plan.dataset_id != package.dataset.id
        ):
            raise HTTPException(409, "El planificador devolvió referencias incompatibles.")
        # A new proposal must never reuse an earlier approval, even for the same hypothesis.
        plan.id = str(uuid4())
        if plan.technique in {
            "pearson",
            "spearman",
            "chi_square",
            "fisher_exact",
            "t_paired",
            "wilcoxon",
            "t_independent",
            "t_welch",
            "mann_whitney",
            "anova",
            "anova_welch",
            "kruskal_wallis",
            "tukey",
            "games_howell",
            "ancova",
            "linear_regression_simple",
            "linear_regression_multiple",
            "cronbach_alpha",
        }:
            questions = {
                "pearson": pearson_questions,
                "spearman": spearman_questions,
                "chi_square": categorical_association_questions,
                "fisher_exact": categorical_association_questions,
                "t_paired": paired_questions,
                "wilcoxon": paired_questions,
                "t_independent": independent_questions,
                "t_welch": independent_questions,
                "mann_whitney": independent_questions,
                "anova": independent_questions,
                "anova_welch": independent_questions,
                "kruskal_wallis": independent_questions,
                "tukey": independent_questions,
                "games_howell": independent_questions,
                "ancova": ancova_questions,
                "linear_regression_simple": simple_regression_questions,
                "linear_regression_multiple": multiple_regression_questions,
                "cronbach_alpha": reliability_questions,
            }[plan.technique](package, plan.hypothesis_id)
            if questions:
                plan.status = "needs_clarification"
                plan.pending_questions.extend(questions)
        plan = AnalysisPlan.model_validate(plan.model_dump())
        connected = plan.technique in CONNECTED
        record = AnalysisRecord(
            project_id=project_id,
            package=package,
            source_version=version,
            proposal_token=self._token(plan, package, version),
            plan=plan,
            created_at=datetime.now(UTC),
            executable=connected and plan.status == "proposed",
            limitation=(
                "La técnica está implementada en Statistics, pero su adaptador de integración "
                "está pendiente. No se puede aprobar ni ejecutar desde Research."
                if plan.technique and not connected
                else None
            ),
        )
        self._current(record)
        self.repository.add(record)
        return record

    def list(self, project_id: UUID) -> list[AnalysisRecord]:
        self.bridge.projects.get(project_id)
        records = self.repository.list(project_id)
        for record in records:
            try:
                # Listing preserves historical records after a local grant expires;
                # approval, execution and export still re-check authorization.
                self._current(record, require_authorization=False)
            except ResearchInputError as exc:
                self._invalidate(project_id, record.plan.id, str(exc))
        return self.repository.list(project_id)

    def approve(self, project_id: UUID, plan_id: str, approval: ApprovalRequest) -> AnalysisRecord:
        with self._edit_current(project_id, plan_id) as (record, package):
            if approval.proposal_token != record.proposal_token:
                raise HTTPException(409, "La confirmación no corresponde a esta propuesta.")
            if not record.executable or record.plan.status == "needs_clarification":
                raise HTTPException(409, "Resuelve las aclaraciones o el adaptador pendiente.")
            self.bridge.read_dataset(project_id, package, package.dataset)
            if record.plan.status == "proposed":
                record.plan.status = "approved"
                record.approved_at = datetime.now(UTC)
        return record

    def completed_report(self, project_id: UUID, plan_id: str, result_id: str) -> AnalysisRecord:
        """Read persisted completed output; never calculate during a download."""
        with self._edit_current(project_id, plan_id) as (record, package):
            result = record.result
            if result is None or result.id != result_id:
                raise HTTPException(404, "No se encontró el resultado de este plan.")
            if (
                result.status != "completed"
                or record.plan.status != "approved"
                or record.approved_at is None
                or not record.executable
            ):
                raise HTTPException(409, "Solo se exportan análisis aprobados y completados.")
            if result.analysis_plan_id != plan_id or result.dataset_id != package.dataset.id:
                raise HTTPException(
                    409, "El resultado no corresponde al plan y dataset del proyecto."
                )
            return record.model_copy(deep=True)

    def authorized_scatter(
        self, project_id: UUID, plan_id: str, result_id: str
    ) -> AuthorizedScatterPlot:
        """Return bounded raw pairs only for a current, authorized association result.

        This intentionally does not expose a generic dataset endpoint. The data
        is restricted to the two approved variables and remains protected by
        the same local, package/version-bound authorization used for execution.
        """

        with self._edit_current(project_id, plan_id) as (record, package):
            result = record.result
            if result is None or result.id != result_id or result.status != "completed":
                raise HTTPException(404, "No se encontró un resultado completado para el gráfico.")
            if (
                record.plan.status != "approved"
                or record.approved_at is None
                or not record.executable
                or result.analysis_plan_id != plan_id
                or result.dataset_id != package.dataset.id
            ):
                raise HTTPException(409, "Solo se visualizan análisis aprobados y vigentes.")
            if record.plan.technique not in {"pearson", "spearman"}:
                raise HTTPException(
                    409, "El gráfico de dispersión solo está disponible para Pearson o Spearman."
                )
            hypothesis = next(
                (item for item in package.hypotheses if item.id == record.plan.hypothesis_id),
                None,
            )
            variables = {item.id: item for item in package.variables}
            if hypothesis is None or len(hypothesis.variable_ids) != 2:
                raise HTTPException(
                    409, "Las variables aprobadas ya no permiten un gráfico válido."
                )
            try:
                left, right = [variables[item_id] for item_id in hypothesis.variable_ids]
                left_column, right_column = left.columns[0], right.columns[0]
                table = BytesDatasetReader(
                    lambda reference: self.bridge.read_dataset(project_id, package, reference)
                ).read(package.dataset)
                left_index, right_index = (
                    table.columns.index(left_column),
                    table.columns.index(right_column),
                )
            except (KeyError, IndexError, ValueError) as exc:
                raise HTTPException(409, "Las columnas aprobadas ya no están disponibles.") from exc

            pairs: list[AuthorizedScatterPoint] = []
            for row in table.rows:
                try:
                    x, y = float(row[left_index]), float(row[right_index])
                except (TypeError, ValueError):
                    continue
                if math.isfinite(x) and math.isfinite(y):
                    pairs.append(AuthorizedScatterPoint(x=x, y=y))
            if not pairs:
                raise HTTPException(409, "No hay pares numéricos completos para visualizar.")
            step = max(1, math.ceil(len(pairs) / self._MAX_SCATTER_POINTS))
            return AuthorizedScatterPlot(
                x_label=left_column,
                y_label=right_column,
                points=pairs[::step],
                complete_pair_count=len(pairs),
                sampled=step > 1,
            )

    def authorized_residuals(
        self, project_id: UUID, plan_id: str, result_id: str
    ) -> AuthorizedResidualPlot:
        """Return a bounded residual diagnostic for one approved linear model.

        There is deliberately no generic data route: feature construction is
        restricted to the plan's approved variables and matches the engine's
        deterministic regression/ANCOVA encoding.
        """

        with self._edit_current(project_id, plan_id) as (record, package):
            result = record.result
            if result is None or result.id != result_id or result.status != "completed":
                raise HTTPException(404, "No se encontró un resultado completado para el gráfico.")
            if (
                record.plan.status != "approved"
                or record.approved_at is None
                or not record.executable
                or result.analysis_plan_id != plan_id
                or result.dataset_id != package.dataset.id
            ):
                raise HTTPException(409, "Solo se visualizan análisis aprobados y vigentes.")
            if record.plan.technique not in {
                "linear_regression_simple",
                "linear_regression_multiple",
                "ancova",
            }:
                raise HTTPException(
                    409,
                    "El gráfico de residuos solo está disponible para regresiones o ANCOVA.",
                )
            hypothesis = next(
                (item for item in package.hypotheses if item.id == record.plan.hypothesis_id),
                None,
            )
            variables = {item.id: item for item in package.variables}
            if hypothesis is None:
                raise HTTPException(
                    409, "Las variables aprobadas ya no permiten un gráfico válido."
                )
            try:
                selected = [variables[item_id] for item_id in hypothesis.variable_ids]
                outcome_variable = next(item for item in selected if item.role == "dependent")
                outcome_column = outcome_variable.columns[0]
                table = BytesDatasetReader(
                    lambda reference: self.bridge.read_dataset(project_id, package, reference)
                ).read(package.dataset)
                outcome_index = table.columns.index(outcome_column)
            except (KeyError, IndexError, StopIteration, ValueError) as exc:
                raise HTTPException(409, "Las columnas aprobadas ya no están disponibles.") from exc

            features: list[list[float]] = []
            outcomes: list[float] = []
            try:
                if record.plan.technique == "ancova":
                    group = next(item for item in selected if item.role == "independent")
                    covariate = next(item for item in selected if item.role == "covariate")
                    group_index = table.columns.index(group.columns[0])
                    covariate_index = table.columns.index(covariate.columns[0])
                    categories = sorted(
                        {
                            str(row[group_index]).strip()
                            for row in table.rows
                            if row[group_index] is not None and str(row[group_index]).strip()
                        }
                    )
                    if len(categories) < 2:
                        raise ValueError("insufficient groups")
                    for row in table.rows:
                        try:
                            outcome = float(row[outcome_index])
                            covariate_value = float(row[covariate_index])
                        except (TypeError, ValueError):
                            continue
                        current_group = (
                            "" if row[group_index] is None else str(row[group_index]).strip()
                        )
                        if (
                            not current_group
                            or not math.isfinite(outcome)
                            or not math.isfinite(covariate_value)
                        ):
                            continue
                        features.append(
                            [
                                *[
                                    1.0 if current_group == category else 0.0
                                    for category in categories[1:]
                                ],
                                covariate_value,
                            ]
                        )
                        outcomes.append(outcome)
                else:
                    predictors = [
                        item for item in selected if item.role in {"independent", "covariate"}
                    ]
                    predictor_indices = [
                        table.columns.index(item.columns[0]) for item in predictors
                    ]
                    for row in table.rows:
                        try:
                            outcome = float(row[outcome_index])
                            values = [float(row[index]) for index in predictor_indices]
                        except (TypeError, ValueError):
                            continue
                        if math.isfinite(outcome) and all(math.isfinite(value) for value in values):
                            features.append(values)
                            outcomes.append(outcome)
            except (IndexError, ValueError) as exc:
                raise HTTPException(
                    409, "Las columnas aprobadas ya no permiten un gráfico válido."
                ) from exc

            try:
                fitted = linear_fitted_values(features, outcomes)
            except Exception as exc:
                raise HTTPException(
                    409, "El modelo ya no permite calcular residuos válidos."
                ) from exc
            points = [
                AuthorizedResidualPoint(fitted=value, residual=outcome - value)
                for value, outcome in zip(fitted, outcomes, strict=True)
            ]
            if not points:
                raise HTTPException(409, "No hay observaciones completas para visualizar.")
            step = max(1, math.ceil(len(points) / self._MAX_SCATTER_POINTS))
            return AuthorizedResidualPlot(
                outcome_label=outcome_column,
                points=points[::step],
                complete_observation_count=len(points),
                sampled=step > 1,
            )

    def execute(self, project_id: UUID, plan_id: str) -> AnalysisResult:
        with self._edit_current(project_id, plan_id) as (record, package):
            if record.plan.status != "approved" or record.approved_at is None:
                raise HTTPException(409, "Aprueba explícitamente el plan antes de ejecutarlo.")
            if not record.executable or record.plan.technique not in CONNECTED:
                raise HTTPException(409, "El adaptador de esta técnica está pendiente.")
            if record.result is not None:
                return record.result
            reader = BytesDatasetReader(
                lambda reference: self.bridge.read_dataset(project_id, package, reference)
            )
            try:
                inputs = {}
                if record.plan.technique in {
                    "pearson",
                    "spearman",
                    "chi_square",
                    "fisher_exact",
                    "t_paired",
                    "wilcoxon",
                    "t_independent",
                    "t_welch",
                    "mann_whitney",
                    "anova",
                    "anova_welch",
                    "kruskal_wallis",
                    "tukey",
                    "games_howell",
                    "ancova",
                    "linear_regression_simple",
                    "linear_regression_multiple",
                    "cronbach_alpha",
                }:
                    table = reader.read(package.dataset)
                    inputs[plan_id] = analysis_input(package, record.plan, table)
                    engine = DeterministicStatisticalEngine(
                        reader, {package.dataset.id: package.dataset}, inputs
                    )
                else:
                    engine = build_engine_from_research_bridge(self.bridge, project_id, package)
                result = engine.execute(record.plan)
            except ResearchInputError:
                raise
            except HTTPException:
                raise
            except Exception:
                logger.exception("Research analysis engine failed")
                result = AnalysisResult(
                    schema_version="1.0.0",
                    id=f"result-{plan_id}",
                    analysis_plan_id=plan_id,
                    dataset_id=package.dataset.id,
                    status="failed",
                    engine_version=DeterministicStatisticalEngine.VERSION,
                    warnings=[
                        "El motor no pudo completar el análisis. Revisa los datos y el plan."
                    ],
                )
            result = AnalysisResult.model_validate(result.model_dump())
            if result.analysis_plan_id != plan_id or result.dataset_id != package.dataset.id:
                raise HTTPException(409, "El resultado no corresponde al plan y dataset aprobados.")
            if record.plan.technique in {"pearson", "spearman"} and result.status == "completed":
                n = next(metric.value for metric in result.metrics if metric.name == "n")
                if n < package.dataset.row_count:
                    result.warnings.append(
                        f"{record.plan.technique} utilizó {int(n)} de "
                        f"{package.dataset.row_count} filas: "
                        "se excluyeron pares incompletos según la política del motor."
                    )
                result.warnings.append(
                    "Se informa el coeficiente de asociación y un p-valor bilateral aproximado. "
                    "Revisa monotonicidad, independencia y valores atípicos antes de interpretar."
                    if record.plan.technique == "spearman"
                    else "Se informa el coeficiente r y un p-valor bilateral. Revisa linealidad, "
                    "normalidad y valores atípicos antes de interpretar."
                )
            record.result = result
        return result
