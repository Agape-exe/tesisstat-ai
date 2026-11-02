"""Research → planner → explicit approval → real engine, local synthetic data only."""

import hashlib
import json
import logging
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.modules.research.documents.repository import DocumentRepository
from app.modules.research.documents.sqlite_repository import DocumentStorageError
from app.modules.statistics.composition import build_engine_from_research_bridge
from app.modules.statistics.engine import DeterministicStatisticalEngine
from app.modules.statistics.planner import DeterministicStatisticalPlanner, UnknownHypothesis
from app.modules.statistics.research_bridge import BytesDatasetReader
from app.orchestration.analysis_inputs import (
    CONNECTED,
    analysis_input,
    categorical_association_questions,
    independent_questions,
    paired_questions,
    pearson_questions,
    reliability_questions,
    spearman_questions,
)
from app.orchestration.analysis_models import AnalysisRecord, ApprovalRequest, PlanRequest
from app.orchestration.analysis_repository import SQLiteAnalysisRepository
from app.orchestration.research_statistics import ResearchInputError, ResearchStatisticsBridge
from app.shared.contracts import AnalysisPlan, AnalysisResult, ResearchPackage

logger = logging.getLogger(__name__)


class ResearchAnalysisService:
    def __init__(
        self,
        bridge: ResearchStatisticsBridge,
        repository: SQLiteAnalysisRepository,
        documents: DocumentRepository,
    ):
        self.bridge = bridge
        self.repository = repository
        self.documents = documents
        self.planner = DeterministicStatisticalPlanner()

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

    @staticmethod
    def _synthetic(package: ResearchPackage) -> None:
        if not package.dataset.synthetic:
            raise HTTPException(403, "Esta integración de desarrollo solo admite datos sintéticos.")

    def _current(self, record: AnalysisRecord) -> ResearchPackage:
        if record.invalidated_at:
            raise ResearchInputError("plan_stale", record.stale_reason or "El plan está obsoleto.")
        package = self.bridge.get_package(record.project_id, record.plan.research_package_id)
        if (
            package != record.package
            or self._version(record.project_id) != record.source_version
            or record.plan.hypothesis_id not in {item.id for item in package.hypotheses}
            or record.plan.dataset_id != package.dataset.id
            or record.proposal_token != self._token(record.plan, package, record.source_version)
        ):
            raise ResearchInputError("plan_stale", "Las fuentes o la propuesta del plan cambiaron.")
        self._synthetic(package)
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
        self._synthetic(package)
        version = self._version(project_id)
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
            "mann_whitney",
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
                "mann_whitney": independent_questions,
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
                self._current(record)
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
                    "mann_whitney",
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
                    "Se informa solo el coeficiente de asociación; no se calculó p-valor "
                    "ni significancia. Revisa monotonicidad, normalidad y valores atípicos "
                    "antes de interpretar."
                    if record.plan.technique == "spearman"
                    else "Se informa solo el coeficiente r; no se calculó p-valor ni "
                    "significancia. Revisa linealidad, normalidad y valores atípicos "
                    "antes de interpretar."
                )
            record.result = result
        return result
