"""Intermediate extraction models and evidence validation for research instruments.

Defines the unconfirmed, intermediate representations produced during document
extraction (PDF/DOCX) prior to human review. Strictly forbids inventing dimensions,
indicators, or numeric codings when not explicitly documented in the source.

Architectural Notice (Separation of Document Provenance):
In a thesis project, the questionnaire/instrument often resides in an appendix
document (e.g., 'Anexo 1 - Cuestionario.docx' or a separate PDF) distinct from the
main thesis monograph where the research methodology is described.
These models explicitly decouple:
- `instrument_document_id`: the actual document containing the instrument items.
- `methodology_document_id`: the document where MethodologyReview was conducted.
This paves the way for 18A-4.3 to link both documents without cross-contamination.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Sha256Hex = Annotated[
    str,
    StringConstraints(
        pattern=r"^[a-f0-9]{64}$",
        strip_whitespace=True,
    ),
]


class UnverifiableEvidenceError(ValueError):
    """Raised when evidence verification fails under strict mode."""

    pass


class SourceReference(BaseModel):
    """Verifiable textual citation pointing directly to original document text."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    field: str = Field(min_length=1, max_length=200)
    document_id: UUID
    quote: str = Field(min_length=1, max_length=1000)
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    verified: bool = False
    warning: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_offsets(self) -> SourceReference:
        if self.verified:
            if self.start is None or self.end is None:
                raise ValueError("Una evidencia verificada requiere 'start' y 'end'.")
            if self.start >= self.end:
                raise ValueError("'start' debe ser estrictamente menor que 'end'.")
        return self


class ExtractedResponseOption(BaseModel):
    """Response option extracted from an item or questionnaire scale header.

    If the document only provides categorical labels (e.g., 'Totalmente de acuerdo')
    without explicit numeric assignments, numeric_value remains None. Never fabricate
    values such as 1, 2, 3, 4, 5.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str | None = Field(default=None, max_length=100)
    label: str = Field(min_length=1, max_length=200)
    numeric_value: float | None = None
    evidence_quote: str | None = Field(default=None, max_length=1000)

    @field_validator("numeric_value")
    @classmethod
    def validate_numeric(cls, v: float | None) -> float | None:
        if v is not None and not math.isfinite(v):
            raise ValueError("numeric_value debe ser un número finito (no NaN ni infinito).")
        return v


class ExtractedVariable(BaseModel):
    """Documented variable explicitly found in the instrument section."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    variable_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=200)
    role: Literal["independent", "dependent", "covariate", "descriptive", "unknown"] = "unknown"
    scale: Literal["nominal", "ordinal", "interval", "ratio", "unknown"] = "unknown"
    evidence_quote: str | None = Field(default=None, max_length=1000)


class ExtractedDimension(BaseModel):
    """Documented dimension explicitly identified in the source text.

    If the source document does not specify dimensions, this list remains empty.
    Do NOT create artificial dimensions (e.g. 'General' or 'Sin dimensión').
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    dimension_id: UUID = Field(default_factory=uuid4)
    variable_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    evidence_quote: str | None = Field(default=None, max_length=1000)


class ExtractedIndicator(BaseModel):
    """Documented indicator explicitly identified in the source text.

    If the source document does not specify indicators, this list remains empty.
    Do NOT create artificial indicators.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    indicator_id: UUID = Field(default_factory=uuid4)
    dimension_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    evidence_quote: str | None = Field(default=None, max_length=1000)


class ExtractedItem(BaseModel):
    """Questionnaire item or prompt extracted from document.

    Preserves missing dimensions, indicators, or numeric codes without fabricating them.
    All missing attributes are captured in pending_fields for subsequent human review.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    item_id: UUID = Field(default_factory=uuid4)
    item_number: int | None = Field(default=None, ge=1)
    text: str = Field(min_length=1, max_length=1000)
    variable_id: UUID | None = None
    dimension_id: UUID | None = None
    indicator_id: UUID | None = None
    response_type: Literal["single_choice", "numeric", "unknown"] = "unknown"
    response_options: list[ExtractedResponseOption] = Field(default_factory=list)
    valid_min: float | None = None
    valid_max: float | None = None
    reverse_scored: bool = False
    reverse_rule: Literal["min_plus_max_minus_value"] | None = None
    source_quote: str | None = Field(default=None, max_length=1000)
    pending_fields: list[str] = Field(default_factory=list)

    @field_validator("valid_min", "valid_max")
    @classmethod
    def validate_bounds(cls, v: float | None) -> float | None:
        if v is not None and not math.isfinite(v):
            raise ValueError("Los límites válidos deben ser números finitos.")
        return v

    @model_validator(mode="after")
    def validate_item_state(self) -> ExtractedItem:
        if self.valid_min is not None and self.valid_max is not None:
            if self.valid_min >= self.valid_max:
                raise ValueError("valid_min debe ser estrictamente menor que valid_max.")

        # Inversion rule coherence: only permitted if reverse_scored is True
        if self.reverse_scored:
            if self.reverse_rule != "min_plus_max_minus_value":
                raise ValueError(
                    "Los ítems con puntuación invertida requieren la regla "
                    "'min_plus_max_minus_value'."
                )
            if self.valid_min is None or self.valid_max is None:
                raise ValueError(
                    "Los ítems con puntuación invertida requieren declarar "
                    "explícitamente valid_min y valid_max."
                )
        else:
            if self.reverse_rule is not None:
                raise ValueError(
                    "Los ítems no invertidos no deben declarar una regla de inversión."
                )

        # Detect pending fields for transparency
        detected_pending: list[str] = []
        if self.variable_id is None:
            detected_pending.append("variable_id")
        if self.dimension_id is None:
            detected_pending.append("dimension_id")
        if self.indicator_id is None:
            detected_pending.append("indicator_id")
        if self.response_type == "unknown":
            detected_pending.append("response_type")
        elif self.response_type == "single_choice":
            if not self.response_options:
                detected_pending.append("response_options")
            else:
                for idx, opt in enumerate(self.response_options):
                    if opt.numeric_value is None:
                        detected_pending.append(f"response_options.{idx}.numeric_value")
                    if opt.code is None:
                        detected_pending.append(f"response_options.{idx}.code")
        elif self.response_type == "numeric":
            if self.valid_min is None:
                detected_pending.append("valid_min")
            if self.valid_max is None:
                detected_pending.append("valid_max")

        for p in detected_pending:
            if p not in self.pending_fields:
                self.pending_fields.append(p)

        return self


class ExtractedScoringRule(BaseModel):
    """Scoring or aggregation rule documented in the instrument.

    Extracted rules are NEVER pre-confirmed. They require explicit human verification.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scoring_rule_id: UUID = Field(default_factory=uuid4)
    name: str | None = Field(default=None, max_length=200)
    scope: Literal["dimension", "instrument", "unknown"] = "unknown"
    dimension_id: UUID | None = None
    item_ids: list[UUID] = Field(default_factory=list)
    aggregation: Literal["sum", "mean", "unknown"] = "unknown"
    missing_policy: Literal["all_required"] = "all_required"
    confirmed: bool = False
    evidence_quote: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_rule(self) -> ExtractedScoringRule:
        if self.confirmed:
            raise ValueError("Las reglas extraídas de documentos no pueden nacer confirmadas.")
        return self


class CandidateInstrument(BaseModel):
    """Candidate psychometric or evaluation instrument identified within a document."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    candidate_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    target_variable_name: str | None = Field(default=None, max_length=200)
    variables: list[ExtractedVariable] = Field(default_factory=list)
    dimensions: list[ExtractedDimension] = Field(default_factory=list)
    indicators: list[ExtractedIndicator] = Field(default_factory=list)
    items: list[ExtractedItem] = Field(default_factory=list)
    scoring_rules: list[ExtractedScoringRule] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    pending_fields: list[str] = Field(default_factory=list)
    is_complete: bool = False

    @model_validator(mode="after")
    def calculate_completeness_and_pending(self) -> CandidateInstrument:
        pending: list[str] = []

        if not self.variables:
            pending.append("variables")
        if not self.dimensions:
            pending.append("dimensions")
        if not self.indicators:
            pending.append("indicators")
        if not self.items:
            pending.append("items")
        else:
            for idx, item in enumerate(self.items):
                for p in item.pending_fields:
                    pending.append(f"items.{idx}.{p}")

        # Scoring rules are optional for structural completeness:
        # Academic instruments may be reviewed and structurally valid without scoring rules.
        # If rules exist, any incomplete rule preserves its pending fields.
        for idx, rule in enumerate(self.scoring_rules):
            if rule.scope == "unknown":
                pending.append(f"scoring_rules.{idx}.scope")
            if rule.aggregation == "unknown":
                pending.append(f"scoring_rules.{idx}.aggregation")
            if not rule.item_ids:
                pending.append(f"scoring_rules.{idx}.item_ids")

        for p in pending:
            if p not in self.pending_fields:
                self.pending_fields.append(p)

        # Structural completeness check: is_complete is True only if:
        # 1. At least 1 variable, dimension, indicator, and item exist.
        # 2. No pending fields on any item.
        # 3. If any scoring rule exists, it must not have pending fields.
        # Note: Absence of scoring_rules does NOT mark instrument incomplete.
        has_items = len(self.items) > 0
        has_vars = len(self.variables) > 0
        has_dims = len(self.dimensions) > 0
        has_inds = len(self.indicators) > 0

        no_item_pending = all(len(it.pending_fields) == 0 for it in self.items)
        no_rule_pending = all(
            r.scope != "unknown" and r.aggregation != "unknown" and len(r.item_ids) > 0
            for r in self.scoring_rules
        )

        self.is_complete = bool(
            has_items and has_vars and has_dims and has_inds and no_item_pending and no_rule_pending
        )
        return self

    @property
    def is_structurally_complete(self) -> bool:
        """Indica si el instrumento cumple con la estructura mínima válida."""
        return self.is_complete

    @property
    def has_operational_scoring(self) -> bool:
        """Indica si cuenta con reglas de puntuación completas para cálculo compuesto.

        Distingue la preparación operacional de la completitud estructural.
        Si una operación estadística requiere reglas compuestas, Statistics validará
        esta precondición.
        """
        return len(self.scoring_rules) > 0 and all(
            r.scope != "unknown" and r.aggregation != "unknown" and len(r.item_ids) > 0
            for r in self.scoring_rules
        )


class InstrumentSourceProvenance(BaseModel):
    """Decoupled provenance separating the instrument file from the methodology document."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    instrument_document_id: UUID
    instrument_document_hash: Sha256Hex
    methodology_document_id: UUID | None = None
    methodology_review_version: int | None = Field(default=None, ge=0)
    methodology_review_hash: Sha256Hex | None = None
    separation_notes: str | None = Field(default=None, max_length=500)


class DocumentInstrumentExtraction(BaseModel):
    """Aggregate result of instrument extraction for a specific document."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: UUID
    document_id: UUID
    provenance: InstrumentSourceProvenance
    status: Literal[
        "completed",
        "no_instruments_found",
        "insufficient_text",
        "failed",
        "stale",
    ] = "completed"
    instruments: list[CandidateInstrument] = Field(default_factory=list)
    evidences: list[SourceReference] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    pending_fields: list[str] = Field(default_factory=list)
    truncated: bool = False
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_extraction_summary(self) -> DocumentInstrumentExtraction:
        if self.status == "no_instruments_found":
            if self.instruments:
                raise ValueError("Un estado 'no_instruments_found' no debe incluir instrumentos.")
            if not any("No se identificaron instrumentos" in w for w in self.warnings):
                self.warnings.append(
                    "No se identificaron instrumentos estructurados en el documento."
                )
        elif self.status == "completed":
            if not self.instruments:
                self.status = "no_instruments_found"
                self.warnings.append(
                    "No se identificaron instrumentos estructurados en el documento."
                )

        # Aggregate pending fields from all candidate instruments
        all_pending: list[str] = list(self.pending_fields)
        for idx, inst in enumerate(self.instruments):
            for p in inst.pending_fields:
                key = f"instruments.{idx}.{p}"
                if key not in all_pending:
                    all_pending.append(key)
        self.pending_fields = all_pending
        return self


class EvidenceValidationResult(BaseModel):
    """Result of textual evidence verification against extracted source document text."""

    model_config = ConfigDict(extra="forbid")

    total_quotes_checked: int = 0
    verified_quotes_count: int = 0
    unverified_quotes_count: int = 0
    references: list[SourceReference] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def validate_extraction_evidence(
    extraction: DocumentInstrumentExtraction,
    source_text: str,
    strict: bool = False,
) -> EvidenceValidationResult:
    """Verifies all textual quotes in an extraction against the raw source text.

    Calculates exact start and end offsets without fabricating fake values.
    Supports secure disambiguation when quotes repeat across the document:
    - If origin provides verified offsets, validates that source_text[start:end] == quote.
    - If offsets are provided but do not match verbatim, marks evidence unverified.
    - If no offsets are provided and the quote appears exactly once, assigns verified offsets.
    - If no offsets are provided and multiple matches exist, flags ambiguity without
      silently choosing the first occurrence.
    - If strict=True, raises UnverifiableEvidenceError on missing, ambiguous, or mismatched quotes.
    """
    references: list[SourceReference] = []
    warnings: list[str] = []
    doc_id = extraction.document_id

    # Index any pre-existing references by field path to check provided offsets
    provided_refs: dict[str, SourceReference] = {
        ref.field: ref for ref in extraction.evidences if ref.document_id == doc_id
    }

    # Gather quote targets across candidate instruments
    targets: list[tuple[str, str]] = []  # (field_path, quote)

    for i_idx, inst in enumerate(extraction.instruments):
        for v_idx, var in enumerate(inst.variables):
            if var.evidence_quote:
                targets.append(
                    (f"instruments.{i_idx}.variables.{v_idx}.evidence_quote", var.evidence_quote)
                )
        for d_idx, dim in enumerate(inst.dimensions):
            if dim.evidence_quote:
                targets.append(
                    (f"instruments.{i_idx}.dimensions.{d_idx}.evidence_quote", dim.evidence_quote)
                )
        for ind_idx, ind in enumerate(inst.indicators):
            if ind.evidence_quote:
                targets.append(
                    (
                        f"instruments.{i_idx}.indicators.{ind_idx}.evidence_quote",
                        ind.evidence_quote,
                    )
                )
        for it_idx, item in enumerate(inst.items):
            if item.source_quote:
                targets.append(
                    (f"instruments.{i_idx}.items.{it_idx}.source_quote", item.source_quote)
                )
            for opt_idx, opt in enumerate(item.response_options):
                if opt.evidence_quote:
                    targets.append(
                        (
                            f"instruments.{i_idx}.items.{it_idx}.options.{opt_idx}.evidence_quote",
                            opt.evidence_quote,
                        )
                    )
        for r_idx, rule in enumerate(inst.scoring_rules):
            if rule.evidence_quote:
                targets.append(
                    (
                        f"instruments.{i_idx}.scoring_rules.{r_idx}.evidence_quote",
                        rule.evidence_quote,
                    )
                )

    verified_count = 0
    unverified_count = 0

    for field_path, quote in targets:
        clean_quote = quote.strip()
        if not clean_quote:
            continue

        # Check if the origin provided explicit offsets
        provided = provided_refs.get(field_path)
        if provided is not None and provided.start is not None and provided.end is not None:
            p_start = provided.start
            p_end = provided.end
            if (
                0 <= p_start < p_end <= len(source_text)
                and source_text[p_start:p_end] == clean_quote
            ):
                # Verifiable location provided by origin
                ref = SourceReference(
                    field=field_path,
                    document_id=doc_id,
                    quote=clean_quote,
                    start=p_start,
                    end=p_end,
                    verified=True,
                    warning=None,
                )
                references.append(ref)
                verified_count += 1
                continue
            else:
                # Provided offsets do not correspond to original text
                unverified_count += 1
                msg = (
                    f"Los offsets [{p_start}:{p_end}] proporcionados para '{field_path}' "
                    "no corresponden al texto original de la cita."
                )
                if strict:
                    raise UnverifiableEvidenceError(msg)
                warnings.append(msg)
                ref = SourceReference(
                    field=field_path,
                    document_id=doc_id,
                    quote=clean_quote,
                    start=None,
                    end=None,
                    verified=False,
                    warning=msg,
                )
                references.append(ref)
                continue

        # Search for occurrences in source_text
        occurrences: list[int] = []
        pos = 0
        while True:
            pos = source_text.find(clean_quote, pos)
            if pos == -1:
                break
            occurrences.append(pos)
            pos += 1

        if len(occurrences) == 0:
            unverified_count += 1
            msg = f"La cita para el campo '{field_path}' no se encuentra en el texto fuente."
            if strict:
                raise UnverifiableEvidenceError(msg)
            warnings.append(msg)
            ref = SourceReference(
                field=field_path,
                document_id=doc_id,
                quote=clean_quote,
                start=None,
                end=None,
                verified=False,
                warning=msg,
            )
            references.append(ref)
        elif len(occurrences) == 1:
            start_pos = occurrences[0]
            end_pos = start_pos + len(clean_quote)
            ref = SourceReference(
                field=field_path,
                document_id=doc_id,
                quote=clean_quote,
                start=start_pos,
                end=end_pos,
                verified=True,
                warning=None,
            )
            references.append(ref)
            verified_count += 1
        else:
            # Multiple matches without disambiguating offsets: do NOT silently assign first
            unverified_count += 1
            msg = (
                f"Cita ambigua para el campo '{field_path}': se encontraron {len(occurrences)} "
                "coincidencias en el texto fuente y no se proporcionaron offsets para desambiguar."
            )
            if strict:
                raise UnverifiableEvidenceError(msg)
            warnings.append(msg)
            ref = SourceReference(
                field=field_path,
                document_id=doc_id,
                quote=clean_quote,
                start=None,
                end=None,
                verified=False,
                warning=msg,
            )
            references.append(ref)

    # Attach verified references and warnings to extraction
    extraction.evidences = references
    for w in warnings:
        if w not in extraction.warnings:
            extraction.warnings.append(w)

    return EvidenceValidationResult(
        total_quotes_checked=len(targets),
        verified_quotes_count=verified_count,
        unverified_quotes_count=unverified_count,
        references=references,
        warnings=warnings,
    )
