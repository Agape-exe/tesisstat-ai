"""Canonical v2 structures. C2 is executable; C4 consumers arrive in S04.

These models never resolve client-supplied references or authorize resources.
Snapshots must be assembled by a server resolver, not accepted as trusted HTTP input.
"""

import hashlib
import json
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

ID = Annotated[str, Field(min_length=1, max_length=200)]
Text = Annotated[str, Field(max_length=2000)]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Revision = Annotated[int, Field(strict=True, ge=1)]
Design = Literal["experimental", "quasi_experimental", "observational", "unknown"]
Observations = Literal["independent", "paired", "repeated", "unknown"]
Alternative = Literal["two-sided", "greater", "less", "unspecified"]


class V2Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class SourceRef(V2Model):
    kind: Literal[
        "project",
        "context",
        "dataset",
        "dictionary",
        "intent",
        "profile",
        "diagnostic",
        "document",
        "instrument",
        "mapping",
        "score",
        "plan",
        "result",
        "source_file",
        "source_sheet",
        "table",
        "table_context",
        "preparation",
        "snapshot",
    ]
    id: ID
    revision: Revision
    hash: Hash


class Provenance(V2Model):
    kind: Literal["manual", "document", "ai_suggestion", "derived", "unknown"] = "unknown"
    source_refs: list[SourceRef] = Field(default_factory=list)
    algorithm_version: ID | None = None

    @model_validator(mode="after")
    def valid_source(self) -> "Provenance":
        if self.kind == "unknown" and (self.source_refs or self.algorithm_version):
            raise ValueError("Unknown provenance has no sources or algorithm")
        if self.kind == "document" and not any(r.kind == "document" for r in self.source_refs):
            raise ValueError("Document provenance requires a document reference")
        if self.kind == "derived" and (not self.source_refs or not self.algorithm_version):
            raise ValueError("Derived provenance requires sources and algorithm")
        return self


class Confirmation(V2Model):
    actor_ref: ID
    confirmed_at: AwareDatetime
    revision: Revision


class Fact[T](V2Model):
    value: T | None = None
    provenance: Provenance = Field(default_factory=Provenance)
    confirmation: Confirmation | None = None

    @model_validator(mode="after")
    def known_confirmation(self) -> "Fact[T]":
        if self.confirmation and (
            self.value is None or self.value == "unknown" or self.value == ""
        ):
            raise ValueError("Unknown or empty values cannot be confirmed")
        return self


class SpecificObjective(V2Model):
    id: ID
    text: Fact[Text]


class ContextHypothesis(V2Model):
    id: ID
    statement: Fact[Text]
    objective_id: ID | None = None
    alternative: Alternative = Field(
        default="unspecified",
        description=(
            "Antecedente opcional de dirección. Conservar H0/H1 como texto; confirmar "
            "contexto no aprueba prueba unilateral. Resolver y confirmar comparación concreta "
            "por intención."
        ),
    )


class PendingQuestion(V2Model):
    code: ID
    field: ID
    question: Text
    blocks: Literal["profile", "proposal", "execution"]


class ProjectContextV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    project_id: ID
    revision: Annotated[int, Field(strict=True, ge=0)] = 0
    updated_at: AwareDatetime | None = None
    state: Literal["empty", "partial", "usable"] = "empty"
    research_question: Fact[Text] = Field(default_factory=Fact[Text])
    main_objective: Fact[Text] = Field(default_factory=Fact[Text])
    specific_objectives: list[SpecificObjective] = Field(default_factory=list, max_length=40)
    hypotheses: list[ContextHypothesis] = Field(default_factory=list, max_length=40)
    study_description: Fact[Text] = Field(default_factory=Fact[Text])
    data_description: Fact[Text] = Field(default_factory=Fact[Text])
    observational_unit: Fact[Text] = Field(
        default_factory=Fact[Text],
        description=(
            "A quién o qué estudia la investigación en general; opcional. Cada tabla describe "
            "sus filas en row_meaning."
        ),
    )
    sampling_notes: Fact[Text] = Field(default_factory=Fact[Text])
    design: Fact[Design] = Field(default_factory=lambda: Fact[Design](value="unknown"))
    observations: Fact[Observations] = Field(
        default_factory=lambda: Fact[Observations](value="unknown"),
        description=(
            "Antecedente global legado. No establece independencia ni emparejamiento de una "
            "intención."
        ),
    )
    complementary_notes: list[Fact[Text]] = Field(default_factory=list, max_length=20)
    pending_questions: list[PendingQuestion] = Field(default_factory=list)

    @model_validator(mode="after")
    def references(self) -> "ProjectContextV2":
        ids = [o.id for o in self.specific_objectives] + [h.id for h in self.hypotheses]
        if len(ids) != len(set(ids)):
            raise ValueError("Context item IDs must be unique")
        objectives = {o.id for o in self.specific_objectives}
        if any(
            h.objective_id is not None and h.objective_id not in objectives for h in self.hypotheses
        ):
            raise ValueError("Hypothesis references an unknown objective")
        if (self.revision == 0) != (self.updated_at is None):
            raise ValueError("Only virtual context has revision zero and no date")
        return self


class IntentConditions(V2Model):
    inference_reviewed: Fact[Literal["yes", "no", "unknown"]] = Field(
        default_factory=lambda: Fact(value="unknown")
    )
    influence_reviewed: Fact[Literal["yes", "no", "unknown"]] = Field(
        default_factory=lambda: Fact(value="unknown")
    )
    sampling_limit_accepted: Fact[Literal["yes", "no", "unknown"]] = Field(
        default_factory=lambda: Fact(value="unknown")
    )
    review_notes: Fact[Text] = Field(default_factory=Fact[Text])
    linearity: Fact[Literal["yes", "no", "unknown"]] = Field(
        default_factory=lambda: Fact(value="unknown")
    )
    monotonicity: Fact[Literal["yes", "no", "unknown"]] = Field(
        default_factory=lambda: Fact(value="unknown")
    )
    comparable_group_shapes: Fact[Literal["yes", "no", "unknown"]] = Field(
        default_factory=lambda: Fact(value="unknown")
    )
    difference_symmetry: Fact[Literal["yes", "no", "unknown"]] = Field(
        default_factory=lambda: Fact(value="unknown")
    )
    pooled_variance_justified: Fact[Literal["yes", "no", "unknown"]] = Field(
        default_factory=lambda: Fact(value="unknown")
    )


class IntentRole(V2Model):
    variable_id: ID
    role: Literal["outcome", "predictor", "group", "item", "descriptive"]


class PairedColumns(V2Model):
    before_column_id: ID
    after_column_id: ID

    @model_validator(mode="after")
    def distinct(self) -> "PairedColumns":
        if self.before_column_id == self.after_column_id:
            raise ValueError("Paired columns must be distinct")
        return self


class AnalysisIntentV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    revision: Revision
    created_at: AwareDatetime
    updated_at: AwareDatetime
    kind: Literal["descriptive", "association", "comparison", "reliability", "unknown"] = "unknown"
    question: Fact[Text] = Field(default_factory=Fact[Text])
    objective_id: ID | None = None
    hypothesis_id: ID | None = None
    variable_ids: list[ID] = Field(default_factory=list)
    roles: list[IntentRole] = Field(default_factory=list)
    observations: Fact[Observations] = Field(
        default_factory=lambda: Fact(value="unknown"),
        description=(
            "Decisión específica de esta intención: verificar tablas, variables, "
            "identificación, orden y vinculación. No heredar confirmación global de C2."
        ),
    )
    paired_columns: PairedColumns | None = None
    group_column_id: ID | None = None
    alternative: Alternative = "unspecified"
    alpha: Annotated[float, Field(gt=0, lt=1)] = 0.05
    missing_policy: Literal["complete_cases"] = "complete_cases"
    confirmation: Confirmation | None = None
    estimand: Literal[
        "summary",
        "linear_association",
        "monotonic_association",
        "mean_difference",
        "distribution_difference",
        "internal_consistency",
        "unknown",
    ] = "unknown"
    conditions: IntentConditions = Field(default_factory=IntentConditions)
    requested_technique: ID | None = None
    dataset_id: ID | None = None
    observational_unit: Fact[Text] = Field(default_factory=Fact[Text])
    identification: Fact[Text] = Field(default_factory=Fact[Text])
    comparison_notes: Fact[Text] = Field(default_factory=Fact[Text])
    linkage: Fact[Literal["same_row", "unavailable", "unknown"]] = Field(
        default_factory=lambda: Fact(value="unknown")
    )
    identifier_column_id: ID | None = None

    @model_validator(mode="after")
    def references(self) -> "AnalysisIntentV2":
        if len(self.variable_ids) != len(set(self.variable_ids)):
            raise ValueError("Duplicate variables")
        if any(r.variable_id not in self.variable_ids for r in self.roles):
            raise ValueError("Role references an unselected variable")
        role_pairs = [(r.variable_id, r.role) for r in self.roles]
        if len(role_pairs) != len(set(role_pairs)):
            raise ValueError("Duplicate roles")
        if self.kind == "descriptive" and self.alternative != "unspecified":
            raise ValueError("Descriptive intent has no alternative")
        if self.confirmation and (self.kind == "unknown" or self.estimand == "unknown"):
            raise ValueError("Unknown intent cannot be confirmed")
        if self.confirmation and self.confirmation.revision != self.revision:
            raise ValueError("Intent confirmation must match revision")
        return self


class SnapshotVariableV2(V2Model):
    """Selected variable projection; not the full editable S03 dictionary."""

    id: ID
    column_ids: list[ID] = Field(min_length=1)
    name: Fact[Annotated[str, Field(min_length=1, max_length=200)]]
    measurement_scale: Fact[Literal["nominal", "ordinal", "interval", "ratio", "unknown"]]


class AnalysisSnapshotV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    revision: Literal[1] = 1
    created_at: AwareDatetime
    source_refs: list[SourceRef]
    context_ref: SourceRef | None = None
    dictionary_ref: SourceRef
    dataset_ref: SourceRef
    intent_ref: SourceRef
    profile_ref: SourceRef
    diagnostic_refs: list[SourceRef] = Field(default_factory=list)
    instrument_ref: SourceRef | None = None
    score_ref: SourceRef | None = None
    confirmed_facts: dict[str, Fact[Text]] = Field(default_factory=dict)
    variables: list[SnapshotVariableV2] = Field(min_length=1)
    intent: AnalysisIntentV2
    source_fingerprint: Hash
    dependency_fields: list[str] = Field(default_factory=list)
    policy_versions: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def references(self) -> "AnalysisSnapshotV2":
        for field, kind in (
            ("context_ref", "context"),
            ("dictionary_ref", "dictionary"),
            ("dataset_ref", "dataset"),
            ("intent_ref", "intent"),
            ("profile_ref", "profile"),
            ("instrument_ref", "instrument"),
            ("score_ref", "score"),
        ):
            ref = getattr(self, field)
            if ref and (ref.kind != kind or ref not in self.source_refs):
                raise ValueError(f"Invalid {field}")
        if any(r.kind != "diagnostic" or r not in self.source_refs for r in self.diagnostic_refs):
            raise ValueError("Invalid diagnostic refs")
        if self.intent.project_id != self.project_id:
            raise ValueError("Intent belongs to a different project")
        if self.intent.id != self.intent_ref.id or self.intent.revision != self.intent_ref.revision:
            raise ValueError("Intent reference does not match frozen intent")
        if self.intent_ref.hash != canonical_hash(self.intent):
            raise ValueError("Intent hash mismatch")
        if not self.intent.confirmation:
            raise ValueError("Snapshot requires confirmed intent")
        ids = [v.id for v in self.variables]
        if len(ids) != len(set(ids)) or set(ids) != set(self.intent.variable_ids):
            raise ValueError("Snapshot variables must match selected variables")
        if any(not f.confirmation for f in self.confirmed_facts.values()):
            raise ValueError("Snapshot facts must be confirmed")
        if self.source_fingerprint != snapshot_fingerprint(self.source_refs, self.policy_versions):
            raise ValueError("Source fingerprint mismatch")
        return self


def snapshot_fingerprint(refs, versions):
    values = [r.model_dump(mode="json") for r in refs]
    return (
        canonical_hash({"sources": values, "versions": versions})
        if versions
        else canonical_hash(values)
    )


def canonical_hash(value: V2Model | list | dict) -> str:
    """json-sort-v1: editable JSON excludes dates, confirmations and own hash."""
    if isinstance(value, V2Model):
        value = value.model_dump(mode="json")

    def content(item, root=False):
        if isinstance(item, dict):
            return {
                k: content(v)
                for k, v in item.items()
                if k not in {"created_at", "updated_at", "confirmation", "field_confirmations"}
                and not (root and k == "hash")
            }
        if isinstance(item, list):
            return [content(v) for v in item]
        if isinstance(item, datetime):
            return item.isoformat()
        return item

    encoded = json.dumps(
        content(value, root=True),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


V2_CONTRACT_MODELS = (ProjectContextV2, AnalysisIntentV2, AnalysisSnapshotV2)
