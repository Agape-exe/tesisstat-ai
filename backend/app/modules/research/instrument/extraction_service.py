"""Application service for orchestrating document-based research instrument extraction.

Orchestrates the entire pipeline:
Document -> Text extraction -> Fragment selection -> Structured AI provider ->
Evidence validation -> Candidate instruments -> Canonical InstrumentContext draft.

Strictly preserves academic integrity:
- Never fabricates dimensions (e.g. "General"), indicators, or variables.
- Never fabricates numeric response codings (e.g. 1, 2, 3...) when not explicitly in the text.
- Never infers reverse scoring without explicit documentation.
- Never fabricates scoring rules (sum, mean).
- Never automatically confirms instruments or scoring rules via AI.
- Decouples questionnaire document provenance from methodology review document provenance.
- Enforces explicit user consent before any external AI provider invocation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import secrets
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from app.modules.research.documents.extraction import ExtractionResult, ExtractionService
from app.modules.research.documents.models import Document
from app.modules.research.documents.use_cases import DocumentNotFound, DocumentService
from app.modules.research.instrument.contracts import InstrumentContext
from app.modules.research.instrument.extraction_models import (
    CandidateInstrument,
    DocumentInstrumentExtraction,
    InstrumentSourceProvenance,
    validate_extraction_evidence,
)
from app.modules.research.instrument.extraction_provider import (
    FixtureInstrumentProvider,
    InstrumentExtractionProvider,
    InstrumentLanguageModel,
)
from app.modules.research.instrument.fragment_selector import (
    FragmentSelectionLimits,
    select_instrument_fragments,
)
from app.modules.research.instrument.models import (
    InstrumentDimension,
    InstrumentIndicator,
    InstrumentItem,
    InstrumentProvenance,
    InstrumentVariable,
    ResponseOption,
    ScoringRule,
)
from app.modules.research.instrument.service import InstrumentService
from app.modules.research.methodology.repository import MethodologyRepository
from app.modules.research.projects.use_cases import ProjectService


class DocumentExtractionConsentRequired(PermissionError):
    """Raised when external AI invocation is requested without explicit user consent."""

    pass


class IncompleteCandidateError(ValueError):
    """Raised when an incomplete candidate is requested to be converted to canonical draft."""

    pass


class CandidateIntegrityError(ValueError):
    """Raised when candidate integrity validation fails (tampered or unauthenticated)."""

    pass


# Internal server-side secret key for signing candidate integrity tokens.
# Remains strictly within server runtime memory; never exposed to clients.
_SERVER_INTEGRITY_SECRET: bytes = secrets.token_bytes(32)


def compute_candidate_semantic_hash(candidate: CandidateInstrument) -> str:
    """Computes deterministic SHA-256 over all academic and semantic fields of a candidate.

    Excludes candidate_id, document_hash, and integrity_token so that only actual
    extracted structure (variables, dimensions, indicators, items, response options,
    scoring rules, warnings, and citations) contributes to the hash.
    """
    raw = candidate.model_dump(
        mode="json",
        exclude={"candidate_id", "document_hash", "integrity_token"},
    )
    serialized = json.dumps(raw, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_stable_candidate_id(
    project_id: UUID,
    document_id: UUID,
    doc_hash: str,
    candidate: CandidateInstrument,
) -> UUID:
    """Derives a stable, deterministic UUIDv5 for an extracted candidate.

    Guarantees that identical extractions produce the exact same instrument ID,
    while distinct instruments or distinct document provenances produce unique IDs.
    """
    semantic_hash = compute_candidate_semantic_hash(candidate)
    seed = f"tesisstat:candidate:{project_id}:{document_id}:{doc_hash}:{semantic_hash}"
    return uuid5(NAMESPACE_URL, seed)


def generate_candidate_integrity_token(
    project_id: UUID,
    document_id: UUID,
    doc_hash: str,
    candidate: CandidateInstrument,
    secret: bytes = _SERVER_INTEGRITY_SECRET,
) -> str:
    """Produces an HMAC-SHA256 authenticated integrity token binding candidate to document."""
    semantic_hash = compute_candidate_semantic_hash(candidate)
    cand_id = candidate.candidate_id or compute_stable_candidate_id(
        project_id=project_id,
        document_id=document_id,
        doc_hash=doc_hash,
        candidate=candidate,
    )
    msg = f"{project_id}:{document_id}:{doc_hash}:{cand_id}:{semantic_hash}".encode()
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def verify_candidate_integrity_token(
    project_id: UUID,
    document_id: UUID,
    doc_hash: str,
    candidate: CandidateInstrument,
    token: str | None,
    secret: bytes = _SERVER_INTEGRITY_SECRET,
) -> bool:
    """Verifies that the candidate matches the authentic extraction produced by the server."""
    if not token or not isinstance(token, str):
        return False
    expected_cand_id = compute_stable_candidate_id(
        project_id=project_id,
        document_id=document_id,
        doc_hash=doc_hash,
        candidate=candidate,
    )
    if candidate.candidate_id is not None and candidate.candidate_id != expected_cand_id:
        return False
    expected = generate_candidate_integrity_token(
        project_id=project_id,
        document_id=document_id,
        doc_hash=doc_hash,
        candidate=candidate,
        secret=secret,
    )
    return hmac.compare_digest(token, expected)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class InstrumentExtractionService:
    """Application service for orchestrating instrument extraction from research documents."""

    def __init__(
        self,
        projects: ProjectService,
        documents: DocumentService | Any,
        extraction_service: ExtractionService,
        provider: InstrumentExtractionProvider | InstrumentLanguageModel,
        instrument_service: InstrumentService | None = None,
        methodology: MethodologyRepository | None = None,
        fragment_limits: FragmentSelectionLimits | None = None,
        integrity_secret: bytes | None = None,
    ) -> None:
        self.projects = projects
        self.documents = documents
        self.extraction_service = extraction_service
        if isinstance(provider, InstrumentExtractionProvider):
            self.provider = provider
        else:
            self.provider = InstrumentExtractionProvider(model=provider)
        self.instrument_service = instrument_service
        self.methodology = methodology
        self.fragment_limits = fragment_limits or FragmentSelectionLimits()
        self.integrity_secret = integrity_secret or _SERVER_INTEGRITY_SECRET

    def generate_candidate_integrity(
        self,
        project_id: UUID,
        document_id: UUID,
        doc_hash: str,
        candidate: CandidateInstrument,
    ) -> str:
        """Generates an HMAC-SHA256 integrity token using the service's configured secret."""
        return generate_candidate_integrity_token(
            project_id=project_id,
            document_id=document_id,
            doc_hash=doc_hash,
            candidate=candidate,
            secret=self.integrity_secret,
        )

    def verify_candidate_integrity(
        self,
        project_id: UUID,
        document_id: UUID,
        doc_hash: str,
        candidate: CandidateInstrument,
        token: str | None,
    ) -> bool:
        """Verifies candidate integrity using the service's configured secret."""
        return verify_candidate_integrity_token(
            project_id=project_id,
            document_id=document_id,
            doc_hash=doc_hash,
            candidate=candidate,
            token=token,
            secret=self.integrity_secret,
        )

    def _require_project(self, project_id: UUID) -> None:
        self.projects.get(project_id)

    def _get_document(self, project_id: UUID, document_id: UUID) -> Document:
        self._require_project(project_id)
        # Check repository get
        repo = getattr(self.documents, "repository", self.documents)
        doc = repo.get(project_id, document_id)
        if doc is None:
            raise DocumentNotFound(
                f"El documento '{document_id}' no existe o no pertenece al proyecto."
            )
        return doc

    def _read_document_bytes(self, project_id: UUID, document_id: UUID) -> bytes:
        repo = getattr(self.documents, "repository", self.documents)
        return repo.read(project_id, document_id)

    def extract(
        self,
        project_id: UUID,
        document_id: UUID,
        *,
        external_ai_consent: bool = False,
        strict_evidence: bool = False,
        strict_consent: bool = False,
        methodology_document_id: UUID | None = None,
    ) -> DocumentInstrumentExtraction:
        """Extracts candidate research instruments from the specified project document.

        Does NOT persist drafts automatically. Separates extraction/preview from creation.
        """
        # 1. Project and document verification
        self._get_document(project_id, document_id)
        doc_bytes = self._read_document_bytes(project_id, document_id)
        doc_hash = _sha256(doc_bytes)

        # 2. Build decoupled provenance
        methodology_version: int | None = None
        methodology_hash: str | None = None
        if methodology_document_id is not None and self.methodology is not None:
            review = self.methodology.get_review(project_id, methodology_document_id)
            if review is not None and review.review_status == "reviewed":
                methodology_version = review.version
                methodology_hash = _sha256(review.content.model_dump_json().encode())

        provenance = InstrumentSourceProvenance(
            instrument_document_id=document_id,
            instrument_document_hash=doc_hash,
            methodology_document_id=methodology_document_id,
            methodology_review_version=methodology_version,
            methodology_review_hash=methodology_hash,
        )

        # 3. Retrieve or perform text extraction
        text_result: ExtractionResult = self.extraction_service.extract(project_id, document_id)

        if text_result.status == "no_text":
            return DocumentInstrumentExtraction(
                project_id=project_id,
                document_id=document_id,
                provenance=provenance,
                status="insufficient_text",
                instruments=[],
                evidences=[],
                warnings=["El documento no contiene texto legible extraíble; puede requerir OCR."],
                pending_fields=[],
                truncated=text_result.truncated,
            )

        if text_result.status == "failed":
            return DocumentInstrumentExtraction(
                project_id=project_id,
                document_id=document_id,
                provenance=provenance,
                status="failed",
                instruments=[],
                evidences=[],
                warnings=list(text_result.warnings)
                or ["La extracción de texto del documento ha fallado."],
                pending_fields=[],
                truncated=text_result.truncated,
            )

        # 4. Select relevant fragments using heuristic pattern detector
        selector_res = select_instrument_fragments(
            source_text=text_result.text,
            document_id=document_id,
            limits=self.fragment_limits,
        )

        if not selector_res.fragments:
            return DocumentInstrumentExtraction(
                project_id=project_id,
                document_id=document_id,
                provenance=provenance,
                status="no_instruments_found",
                instruments=[],
                evidences=[],
                warnings=[
                    "No se identificaron patrones de instrumentos ni cuestionarios "
                    "en el texto extraído mediante el selector heurístico."
                ]
                + list(selector_res.warnings),
                pending_fields=[],
                truncated=selector_res.truncated,
            )

        # 5. Authorization and Consent Gate
        # Fail-closed: only providers that explicitly declare is_local=True and is_external=False
        # (or are verified offline fixtures) are permitted without external AI consent.
        # Any unknown or unclassified provider defaults to external.
        model = self.provider.model
        is_local_declared = getattr(model, "is_local", False)
        is_external_declared = getattr(model, "is_external", None)

        if is_external_declared is True:
            provider_is_external = True
        elif is_local_declared is True and is_external_declared is False:
            provider_is_external = False
        elif isinstance(model, FixtureInstrumentProvider):
            provider_is_external = False
        else:
            # Fail-closed for unknown or custom provider without explicit is_local=True
            provider_is_external = True

        if provider_is_external and not external_ai_consent:
            msg = (
                "Se requiere autorización explícita para enviar el contenido documental "
                "al proveedor de IA externo. El consentimiento de conversación no se reutiliza "
                "automáticamente."
            )
            if strict_consent:
                raise DocumentExtractionConsentRequired(msg)
            return DocumentInstrumentExtraction(
                project_id=project_id,
                document_id=document_id,
                provenance=provenance,
                status="failed",
                instruments=[],
                evidences=[],
                warnings=[msg] + list(selector_res.warnings),
                pending_fields=[],
                truncated=selector_res.truncated,
            )

        # 6. Structured Provider Invocation
        source_truncated = bool(text_result.truncated or selector_res.truncated)
        extraction = self.provider.extract_from_fragments(
            fragments=selector_res.fragments,
            provenance=provenance,
            project_id=project_id,
            document_id=document_id,
            source_truncated=source_truncated,
        )

        # Append any selector warnings
        for w in selector_res.warnings:
            if w not in extraction.warnings:
                extraction.warnings.append(w)

        # 7. Evidence Verification against raw source text
        if extraction.status == "completed" and extraction.instruments:
            validate_extraction_evidence(
                extraction=extraction,
                source_text=text_result.text,
                strict=strict_evidence,
            )

        # 8. Assign deterministic stable IDs and authenticated integrity tokens to candidates
        for cand in extraction.instruments:
            cand.document_hash = doc_hash
            stable_id = compute_stable_candidate_id(project_id, document_id, doc_hash, cand)
            cand.candidate_id = stable_id
            cand.integrity_token = self.generate_candidate_integrity(
                project_id=project_id,
                document_id=document_id,
                doc_hash=doc_hash,
                candidate=cand,
            )

        return extraction

    def can_convert_to_canonical(
        self,
        candidate: CandidateInstrument,
    ) -> tuple[bool, list[str]]:
        """Verifies if candidate meets all invariants of the canonical InstrumentContext contract.

        Returns (is_valid, list_of_reasons_if_invalid).
        """
        reasons: list[str] = []

        if not candidate.is_complete:
            reasons.append("El candidato no está estructuralmente completo.")

        if not candidate.variables:
            reasons.append("No contiene variables documentadas.")
        if not candidate.dimensions:
            reasons.append("No contiene dimensiones documentadas.")
        if not candidate.indicators:
            reasons.append("No contiene indicadores documentados.")
        if not candidate.items:
            reasons.append("No contiene ítems documentados.")

        var_ids = {v.variable_id for v in candidate.variables}
        dim_ids = {d.dimension_id for d in candidate.dimensions}
        ind_ids = {ind.indicator_id for ind in candidate.indicators}
        item_ids = {it.item_id for it in candidate.items}

        for d in candidate.dimensions:
            if d.variable_id is None or d.variable_id not in var_ids:
                reasons.append(f"La dimensión '{d.name}' no tiene una variable asociada válida.")

        for ind in candidate.indicators:
            if ind.dimension_id is None or ind.dimension_id not in dim_ids:
                reasons.append(f"El indicador '{ind.name}' no tiene una dimensión asociada válida.")

        for idx, it in enumerate(candidate.items):
            it_label = f"Ítem {it.item_number or idx + 1}"
            if it.variable_id is None or it.variable_id not in var_ids:
                reasons.append(f"{it_label} no tiene variable_id asignado.")
            if it.dimension_id is None or it.dimension_id not in dim_ids:
                reasons.append(f"{it_label} no tiene dimension_id asignado.")
            if it.indicator_id is None or it.indicator_id not in ind_ids:
                reasons.append(f"{it_label} no tiene indicator_id asignado.")

            if it.response_type not in ("single_choice", "numeric"):
                reasons.append(
                    f"{it_label} tiene tipo de respuesta no soportado ('{it.response_type}')."
                )
            elif it.response_type == "single_choice":
                if len(it.response_options) < 2:
                    reasons.append(
                        f"{it_label} de tipo single_choice requiere al menos 2 alternativas."
                    )
                for opt_idx, opt in enumerate(it.response_options):
                    if not opt.code:
                        reasons.append(f"{it_label} alternativa {opt_idx + 1} carece de código.")
                    if opt.numeric_value is None or not math.isfinite(opt.numeric_value):
                        reasons.append(
                            f"{it_label} alternativa {opt_idx + 1} carece de "
                            "valor numérico comprobable."
                        )

                codes = [o.code for o in it.response_options if o.code]
                if len(codes) != len(set(codes)):
                    reasons.append(f"{it_label} tiene códigos de respuesta duplicados.")

                num_vals = [
                    o.numeric_value for o in it.response_options if o.numeric_value is not None
                ]
                if len(num_vals) != len(set(num_vals)):
                    reasons.append(f"{it_label} tiene valores numéricos de respuesta duplicados.")
            elif it.response_type == "numeric":
                if it.response_options:
                    reasons.append(
                        f"{it_label} de tipo numeric no debe declarar alternativas de selección."
                    )

            if it.reverse_scored:
                if it.reverse_rule != "min_plus_max_minus_value":
                    reasons.append(
                        f"{it_label} invertido requiere la regla 'min_plus_max_minus_value'."
                    )
                if it.valid_min is None or it.valid_max is None:
                    reasons.append(
                        f"{it_label} invertido requiere declarar límites numéricos válidos."
                    )

        # Scoring rules verification (instruments are valid without scoring rules)
        for r_idx, rule in enumerate(candidate.scoring_rules):
            r_label = f"Regla {rule.name or r_idx + 1}"
            if rule.scope not in ("dimension", "instrument"):
                reasons.append(f"{r_label} tiene ámbito desconocido ('{rule.scope}').")
            elif rule.scope == "dimension" and (
                rule.dimension_id is None or rule.dimension_id not in dim_ids
            ):
                reasons.append(f"{r_label} requiere una dimensión existente válida.")
            elif rule.scope == "instrument" and rule.dimension_id is not None:
                reasons.append(f"{r_label} de ámbito instrumento no debe declarar dimension_id.")

            if rule.aggregation not in ("sum", "mean"):
                reasons.append(f"{r_label} tiene agregación desconocida ('{rule.aggregation}').")

            if not rule.item_ids:
                reasons.append(f"{r_label} no contiene ítems vinculados.")
            else:
                for it_id in rule.item_ids:
                    if it_id not in item_ids:
                        reasons.append(f"{r_label} referencia un ítem inexistente ({it_id}).")

        return len(reasons) == 0, reasons

    def create_draft_from_candidate(
        self,
        project_id: UUID,
        document_id: UUID,
        candidate: CandidateInstrument,
        *,
        methodology_document_id: UUID | None = None,
        instrument_id: UUID | None = None,
        expected_document_hash: str | None = None,
        integrity_token: str | None = None,
        strict_integrity: bool = False,
    ) -> InstrumentContext:
        """Persists a canonical InstrumentContext draft from a valid candidate.

        Idempotent and atomic: Re-invocations return existing matching drafts rather than
        duplicating them.
        """
        if self.instrument_service is None:
            raise RuntimeError(
                "InstrumentService no está configurado en InstrumentExtractionService."
            )

        # 1. Structural validity check
        is_valid, reasons = self.can_convert_to_canonical(candidate)
        if not is_valid:
            raise IncompleteCandidateError(
                f"El candidato '{candidate.name}' no cumple los requisitos canónicos: "
                f"{', '.join(reasons)}"
            )

        # 2. Document verification
        self._get_document(project_id, document_id)
        doc_bytes = self._read_document_bytes(project_id, document_id)
        source_doc_hash = _sha256(doc_bytes)

        if expected_document_hash is not None and expected_document_hash != source_doc_hash:
            from app.modules.research.instrument.repository import InstrumentStaleError

            raise InstrumentStaleError(
                "El documento fuente ha sido modificado desde la extracción original (hash stale).",
                reasons=["hash_mismatch"],
            )

        # 3. Candidate integrity verification
        token = integrity_token or candidate.integrity_token
        if strict_integrity:
            if not token or not self.verify_candidate_integrity(
                project_id=project_id,
                document_id=document_id,
                doc_hash=source_doc_hash,
                candidate=candidate,
                token=token,
            ):
                raise CandidateIntegrityError(
                    "La prueba de integridad del candidato no es válida o el contenido "
                    "semántico fue sustituido respecto a la extracción original."
                )
        elif token is not None:
            if not self.verify_candidate_integrity(
                project_id=project_id,
                document_id=document_id,
                doc_hash=source_doc_hash,
                candidate=candidate,
                token=token,
            ):
                raise CandidateIntegrityError(
                    "La prueba de integridad del candidato no es válida o el contenido "
                    "semántico fue sustituido respecto a la extracción original."
                )

        # 4. Derive stable idempotent identity
        stable_id = instrument_id or compute_stable_candidate_id(
            project_id=project_id,
            document_id=document_id,
            doc_hash=source_doc_hash,
            candidate=candidate,
        )

        # 5. Idempotency Check: Avoid duplicating drafts on repeated extraction calls
        existing_drafts = self.instrument_service.list(project_id)
        for existing in existing_drafts:
            if existing.status == "draft":
                if existing.instrument_id == stable_id:
                    return existing

                matches_items = len(existing.items) == len(candidate.items) and all(
                    e.text == c.text for e, c in zip(existing.items, candidate.items, strict=False)
                )
                if matches_items and existing.provenance is not None:
                    if (
                        existing.provenance.source_kind == "document"
                        and existing.provenance.source_document_id == document_id
                        and existing.provenance.source_document_hash == source_doc_hash
                    ):
                        return existing

        # 4. Map variables without fictitious links
        canonical_vars: list[InstrumentVariable] = [
            InstrumentVariable(
                variable_id=v.variable_id,
                name=v.name,
                scale=v.scale,
                methodology_variable_id=None,  # Rule 7: Never auto-link methodology vars
            )
            for v in candidate.variables
        ]

        # 5. Map dimensions without fictitious 'General'
        canonical_dims: list[InstrumentDimension] = [
            InstrumentDimension(
                dimension_id=d.dimension_id,
                variable_id=d.variable_id,  # type: ignore[arg-type]
                name=d.name,
            )
            for d in candidate.dimensions
        ]

        # 6. Map indicators
        canonical_inds: list[InstrumentIndicator] = [
            InstrumentIndicator(
                indicator_id=ind.indicator_id,
                dimension_id=ind.dimension_id,  # type: ignore[arg-type]
                name=ind.name,
            )
            for ind in candidate.indicators
        ]

        # 7. Map items and options
        canonical_items: list[InstrumentItem] = []
        for it in candidate.items:
            opts = [
                ResponseOption(
                    code=opt.code or "",
                    label=opt.label,
                    numeric_value=opt.numeric_value or 0.0,
                )
                for opt in it.response_options
            ]
            canonical_items.append(
                InstrumentItem(
                    item_id=it.item_id,
                    variable_id=it.variable_id,  # type: ignore[arg-type]
                    dimension_id=it.dimension_id,  # type: ignore[arg-type]
                    indicator_id=it.indicator_id,  # type: ignore[arg-type]
                    text=it.text,
                    response_type=it.response_type,  # type: ignore[arg-type]
                    response_options=opts,
                    valid_min=it.valid_min,
                    valid_max=it.valid_max,
                    reverse_scored=it.reverse_scored,
                    reverse_rule=it.reverse_rule,
                    source_quote=it.source_quote,
                )
            )

        # 8. Map scoring rules (strictly unconfirmed)
        canonical_rules: list[ScoringRule] = []
        for r in candidate.scoring_rules:
            canonical_rules.append(
                ScoringRule(
                    scoring_rule_id=r.scoring_rule_id,
                    scope=r.scope,  # type: ignore[arg-type]
                    dimension_id=r.dimension_id,
                    item_ids=r.item_ids,
                    aggregation=r.aggregation,  # type: ignore[arg-type]
                    missing_policy=r.missing_policy,
                    confirmed=False,  # Rule 8: Never confirmed automatically by AI
                )
            )

        # 9. Establish provenance if methodology review is confirmed
        target_m_doc = methodology_document_id or document_id
        provenance: InstrumentProvenance | None = None
        if self.methodology is not None:
            review = self.methodology.get_review(project_id, target_m_doc)
            if review is not None and review.review_status == "reviewed":
                m_hash = _sha256(review.content.model_dump_json().encode())
                provenance = InstrumentProvenance(
                    source_kind="document",
                    source_document_id=document_id,
                    source_document_hash=source_doc_hash,
                    methodology_review_id=target_m_doc,
                    methodology_review_version=review.version,
                    methodology_review_hash=m_hash,
                )

        # 10. Persist draft via InstrumentService with atomic conflict resolution
        try:
            return self.instrument_service.create_draft(
                project_id=project_id,
                variables=canonical_vars,
                dimensions=canonical_dims,
                indicators=canonical_inds,
                items=canonical_items,
                scoring_rules=canonical_rules,
                provenance=provenance,
                instrument_id=stable_id,
            )
        except Exception as exc:
            from app.modules.research.instrument.repository import InstrumentConflict

            if isinstance(exc, InstrumentConflict):
                existing = self.instrument_service.get(project_id, stable_id)
                if existing is not None and existing.status == "draft":
                    return existing
            raise
