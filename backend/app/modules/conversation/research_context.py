"""Project-scoped read adapter. No extraction, profiling, planning or execution here."""

import hashlib
import json
import re
import sqlite3
from collections import Counter
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.modules.research.datasets.sqlite_repository import DatasetStorageError
from app.modules.research.datasets.use_cases import DatasetService
from app.modules.research.documents.sqlite_repository import DocumentStorageError
from app.modules.research.documents.use_cases import DocumentService
from app.modules.research.eda.sqlite_repository import EDAStorageError
from app.modules.research.eda.use_cases import EDANotFound, EDAService
from app.modules.research.methodology.repository import MethodologyRepository
from app.modules.research.packages.use_cases import PackageService
from app.modules.research.preparation.repository import PreparationRepository
from app.modules.research.projects.use_cases import ProjectService
from app.orchestration.analysis_service import ResearchAnalysisService
from app.orchestration.research_statistics import ResearchInputError


class ContextSource(BaseModel):
    kind: str
    id: str
    status: str
    version: str
    links: dict[str, str] = Field(default_factory=dict)
    data: dict = Field(default_factory=dict)

    def reference(self) -> dict:
        return self.model_dump(exclude={"data"}, exclude_defaults=True)


class ResearchContext(BaseModel):
    project_id: UUID
    sources: list[ContextSource]

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()

    def summary(self) -> dict:
        return {
            "project_id": str(self.project_id),
            "snapshot": self.fingerprint,
            "sources": [source.reference() for source in self.sources],
        }


def version(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


# Names and academic text are untrusted data; redact common embedded identifiers as
# defense in depth. This is deliberately NOT a guarantee of personal-data detection.
def safe_text(value: str) -> str:
    try:
        UUID(value)  # Preserve opaque internal references, including numeric UUID segments.
        return value
    except ValueError:
        pass
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[correo omitido]", value)
    return re.sub(r"(?<![\w.])\d{8,}(?![\w.])", "[identificador omitido]", value)


def clean(value):
    if isinstance(value, str):
        return safe_text(value)
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    return value


def private_column(name: str) -> bool:
    return bool(
        re.search(
            r"(^|[\W_])(id|dni|nombre|nombres|apellido|apellidos|correo|email|"
            r"e_mail|name|surname|telefono|phone|direccion|address|codigo|uuid)([\W_]|$)",
            name,
            re.I,
        )
        or "@" in name
        or re.search(r"\d{8,}", name)
    )


NUMERIC_METRICS = {
    "n",
    "r",
    "rho",
    "n_left",
    "n_right",
    "u",
    "w",
    "w_positive",
    "w_negative",
    "h",
    "f_statistic",
    "degrees_of_freedom",
    "degrees_of_freedom_between",
    "degrees_of_freedom_within",
    "mean_difference",
    "t_statistic",
    "chi_square",
    "odds_ratio",
    "p_value",
    "items",
    "alpha",
    "intercept",
    "slope",
    "r_squared",
    "residual_standard_error",
    "predictor_count",
    "group_count",
    "covariate_beta",
    "pair_count",
}
DESCRIPTIVE_METRICS = {
    "valid_count",
    "missing_count",
    "mean",
    "median",
    "mode",
    "variance",
    "standard_deviation",
    "sample_standard_deviation",
    "sample_variance",
    "minimum",
    "maximum",
    "range",
    "q1",
    "q2",
    "q3",
    "p25",
    "p50",
    "p75",
    "iqr",
}


def safe_metric(name: str, columns: set[str]) -> bool:
    return name in NUMERIC_METRICS or any(
        name == f"{column}.{metric}" for column in columns for metric in DESCRIPTIVE_METRICS
    )


class ResearchContextBuilder:
    def __init__(
        self,
        projects: ProjectService,
        documents: DocumentService,
        methodology: MethodologyRepository,
        datasets: DatasetService,
        eda: EDAService,
        packages: PackageService,
        analyses: ResearchAnalysisService,
        preparation: PreparationRepository,
    ):
        self.projects, self.documents, self.methodology = projects, documents, methodology
        self.datasets, self.eda, self.packages = datasets, eda, packages
        self.analyses, self.preparation = analyses, preparation

    def build(self, project_id: UUID) -> ResearchContext:
        project = self.projects.get(project_id)
        try:
            return self._build(project_id)
        except (
            HTTPException,
            OSError,
            sqlite3.Error,
            DatasetStorageError,
            DocumentStorageError,
            EDAStorageError,
        ):
            # An inaccessible source is not evidence that no source exists. Fail
            # closed for academic facts while preserving local history and basic chat.
            return ResearchContext(
                project_id=project_id,
                sources=[
                    ContextSource(
                        kind="project",
                        id=str(project_id),
                        status="current",
                        version=project.updated_at.isoformat(),
                        data=clean({"title": project.title, "program": project.program}),
                    ),
                    ContextSource(
                        kind="sources",
                        id=str(project_id),
                        status="unverified",
                        version="unavailable",
                        data={
                            "action": (
                                "No se pudieron verificar las fuentes. "
                                "Actualiza e intenta de nuevo."
                            )
                        },
                    ),
                ],
            )

    def _build(self, project_id: UUID) -> ResearchContext:
        project = self.projects.get(project_id)
        sources = []

        def add(kind, identifier, status, revision, data=None):
            sources.append(
                ContextSource(
                    kind=kind,
                    id=str(identifier),
                    status=status,
                    version=str(revision),
                    data=clean(data or {}),
                )
            )

        add(
            "project",
            project.id,
            "current",
            project.updated_at.isoformat(),
            {"title": project.title, "program": project.program},
        )
        docs = [doc for doc in self.documents.list(project_id) if doc.project_id == project_id]
        for doc in docs:
            review = self.methodology.get_review(project_id, doc.id)
            if review and review.project_id == project_id and review.document_id == doc.id:
                confirmed = review.review_status == "reviewed" and review.reviewed_at is not None
                data = {"pending_fields": review.pending_fields}
                if confirmed:
                    # Do not send evidence quotations or full document text.
                    for key, finding in review.content:
                        if key == "title":
                            continue
                        if key == "variables":
                            data[key] = [
                                {
                                    "id": str(item.id),
                                    **{
                                        field: (
                                            [f.value for f in value if f.value]
                                            if isinstance(value, list)
                                            else value.value
                                        )
                                        for field, value in item
                                        if field != "id"
                                    },
                                }
                                for item in finding
                            ]
                        else:
                            data[key] = (
                                [item.value for item in finding if item.value]
                                if isinstance(finding, list)
                                else finding.value
                            )
                add(
                    "methodology",
                    doc.id,
                    "confirmed" if confirmed else "draft",
                    review.version,
                    data,
                )
            else:
                state = self.methodology.get(project_id, doc.id)
                add(
                    "methodology",
                    doc.id,
                    "draft" if state and state.draft else "missing",
                    state.draft.source_hash if state and state.draft else "none",
                )
        if not docs:
            add("methodology", project_id, "missing", "none")

        active = [
            d for d in self.datasets.list(project_id) if d.active and d.project_id == project_id
        ]
        dataset = active[0] if len(active) == 1 else None
        allowed_columns = set()
        if dataset:
            allowed_columns = {name for name in dataset.columns if not private_column(name)}
            add(
                "dataset",
                dataset.id,
                "current",
                version(dataset.model_dump(mode="json")),
                {
                    "name": dataset.name,
                    "row_count": dataset.row_count,
                    "column_count": dataset.column_count,
                    "columns": sorted(allowed_columns),
                    "omitted_identifier_columns": len(dataset.columns) - len(allowed_columns),
                    "origin": "derived" if dataset.source_dataset_id else "original",
                    "source_dataset_id": str(dataset.source_dataset_id)
                    if dataset.source_dataset_id
                    else None,
                    "quality_warning_count": len(dataset.warnings),
                },
            )
            if dataset.source_dataset_id:
                prepared = [
                    r
                    for r in self.preparation.list(project_id, dataset.source_dataset_id)
                    if r.project_id == project_id and r.result_id == dataset.id
                ]
                add(
                    "preparation",
                    dataset.id,
                    "prepared" if prepared else "unverified",
                    version([r.prepared_at for r in prepared]),
                    {
                        "operations": [
                            operation.type for r in prepared for operation in r.operations
                        ],
                        "rows_removed": sum(r.rows_removed for r in prepared),
                        "cells_changed": sum(r.cells_changed for r in prepared),
                    },
                )
            else:
                add("preparation", dataset.id, "original", "none")
            stored = self.eda.repository.get(project_id, dataset.id)
            try:
                profile = self.eda.get(project_id, dataset.id) if stored else None
            except EDANotFound:
                profile = None
            if profile and profile.project_id == project_id and profile.dataset_id == dataset.id:
                # Explicit whitelist: never frequencies, examples, min/max or raw rows.
                add(
                    "eda",
                    dataset.id,
                    "current",
                    profile.content_sha256 + profile.rule_version,
                    {
                        "summary": {
                            key: value
                            for key, value in profile.summary.items()
                            if key
                            in {
                                "rows",
                                "columns",
                                "missing",
                                "missing_percentage",
                                "duplicates",
                                "duplicate_percentage",
                                "problem_columns",
                            }
                        },
                        "columns": [
                            {
                                **{
                                    key: col.get(key)
                                    for key in (
                                        "name",
                                        "suggested_type",
                                        "missing",
                                        "missing_percentage",
                                        "constant",
                                    )
                                },
                                "quality_warnings": [
                                    w.get("message", "") for w in col.get("warnings", [])
                                ],
                            }
                            for col in profile.columns
                            if col.get("name") in allowed_columns
                            and not col.get("possible_identifier")
                        ],
                        "quality_warnings": dict(
                            Counter(w.get("severity", "unknown") for w in profile.warnings)
                        ),
                    },
                )
            else:
                add("eda", dataset.id, "stale" if stored else "missing", "none")
        else:
            add("dataset", project_id, "missing" if not active else "unverified", "none")
            add("eda", project_id, "missing", "none")

        status = self.packages.validate(project_id)
        package = self.packages.get_package(project_id) if status.state == "generated" else None
        if package and dataset and package.dataset.id == str(dataset.id):
            add(
                "package",
                package.id,
                "current",
                status.configuration.version,
                {
                    "design": package.design,
                    "observations": package.observations,
                    "sampling_notes": package.sampling_notes,
                    "hypotheses": [
                        h.model_dump(exclude={"schema_version"}) for h in package.hypotheses
                    ],
                    "variables": [
                        v.model_dump(exclude={"schema_version", "questions"})
                        | {"columns": [c for c in v.columns if c in allowed_columns]}
                        for v in package.variables
                    ],
                    "pending_questions": package.pending_questions,
                },
            )
        else:
            add(
                "package",
                status.package_id or project_id,
                status.state,
                status.configuration.version,
                {
                    "action": "Revisar vinculaciones y generar un paquete vigente.",
                    "errors_count": len(status.errors),
                    "warnings_count": len(status.warnings),
                },
            )

        # The public analysis list refreshes records by writing invalidations. Chat
        # must remain read-only: compute historical status from verified sources.
        records = self.analyses.repository.list(project_id)
        for record in records:
            plan, result = record.plan, record.result
            # Validate stored provenance as well as the project-scoped repository lookup.
            if (
                record.project_id != project_id
                or plan.research_package_id != record.package.id
                or plan.dataset_id != record.package.dataset.id
                or plan.hypothesis_id not in {h.id for h in record.package.hypotheses}
            ):
                continue
            # Reuse the existing read-only provenance validator; unlike list(),
            # _current() does not persist invalidations or change approvals.
            invalid_current = False
            try:
                self.analyses._current(record)
            except ResearchInputError:
                invalid_current = True
            except HTTPException as exc:
                if exc.status_code != 403:
                    raise
                # Dataset authorization can expire on restart. Keep unrelated verified
                # sources, but never expose this analysis or change its authorization.
                add("plan", plan.id, "unverified", record.source_version)
                if (
                    result
                    and result.analysis_plan_id == plan.id
                    and result.dataset_id == plan.dataset_id
                ):
                    add("result", result.id, "unverified", version(result.model_dump()))
                    sources[-1].links = {"plan_id": plan.id, "dataset_id": result.dataset_id}
                continue
            historical = bool(
                invalid_current
                or record.invalidated_at
                or package is None
                or dataset is None
                or plan.dataset_id != str(dataset.id)
                or plan.research_package_id != package.id
                or record.package != package
            )
            linked_result = (
                result
                if (
                    result
                    and result.analysis_plan_id == plan.id
                    and result.dataset_id == plan.dataset_id
                )
                else None
            )
            approved = historical or bool(
                plan.status == "approved" and record.approved_at and record.executable
            )
            add(
                "plan",
                plan.id,
                "historical" if historical else plan.status,
                record.source_version,
                {
                    "package_id": plan.research_package_id,
                    "dataset_id": plan.dataset_id,
                    "hypothesis_id": plan.hypothesis_id,
                    "technique": plan.technique,
                    "approval_status": plan.status,
                    "approved_at": record.approved_at,
                    "rationale": plan.rationale,
                    "assumptions_to_check": plan.assumptions_to_check,
                    "pending_questions": plan.pending_questions,
                    "execution_status": linked_result.status
                    if linked_result and approved
                    else "unverified"
                    if result
                    else "not_executed",
                    "limitation": record.limitation,
                },
            )
            if linked_result:
                data = {
                    "plan_id": plan.id,
                    "dataset_id": result.dataset_id,
                    "execution_status": result.status if approved else "unverified",
                }
                if result.status == "completed" and approved:
                    # Category metrics embed actual response values: exclude them even
                    # when they appear aggregated. Only trusted column prefixes survive.
                    columns = {c for c in record.package.dataset.columns if not private_column(c)}
                    metrics = [
                        m.model_dump() for m in result.metrics if safe_metric(m.name, columns)
                    ]
                    data.update(
                        metrics=metrics,
                        omitted_metrics=len(result.metrics) - len(metrics),
                        assumptions=[
                            a.model_dump()
                            for a in result.assumptions
                            if a.name
                            in {
                                "descriptive_input_validation",
                                "normality",
                                "homogeneity",
                                "homoscedasticity",
                            }
                        ],
                        omitted_assumptions=sum(
                            a.name
                            not in {
                                "descriptive_input_validation",
                                "normality",
                                "homogeneity",
                                "homoscedasticity",
                            }
                            for a in result.assumptions
                        ),
                        warnings=result.warnings,
                        interpretation=result.interpretation,
                    )
                elif result.status == "failed":
                    data["warning"] = "Análisis fallido; no hay métricas utilizables."
                add(
                    "result",
                    result.id,
                    "historical" if historical else result.status if approved else "unverified",
                    version(result.model_dump()),
                    data,
                )
                sources[-1].links = {"plan_id": plan.id, "dataset_id": result.dataset_id}
        if not records:
            add("plan", project_id, "missing", "none")
        if not any(s.kind == "result" for s in sources):
            add("result", project_id, "missing", "none")
        # Serialize dates before the bounded prompt selector sees these facts.
        return ResearchContext.model_validate_json(
            ResearchContext(project_id=project_id, sources=sources).model_dump_json()
        )
