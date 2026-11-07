"""Document fragment selector for research instruments.

Extracts verifiable, bounded text fragments containing candidate instruments, questionnaires,
inventories, operationalization tables, Likert scales, and numbered item sequences from
document text (PDF and DOCX), ensuring strict offset fidelity:
    source_text[start:end] == fragment.text
"""

from __future__ import annotations

import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentFragment(BaseModel):
    """Verifiable textual fragment extracted from source document."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str = Field(min_length=1)
    selection_reason: str = Field(min_length=1, max_length=300)
    document_id: UUID | None = None

    @model_validator(mode="after")
    def validate_fragment(self) -> DocumentFragment:
        if self.start >= self.end:
            raise ValueError("'start' debe ser estrictamente menor que 'end'.")
        if len(self.text) != (self.end - self.start):
            raise ValueError("La longitud del texto debe coincidir exactamente con end - start.")
        return self


class FragmentSelectionLimits(BaseModel):
    """Configuration limits and budget bounds for fragment extraction."""

    model_config = ConfigDict(extra="forbid")

    max_total_characters: int = Field(default=8000, ge=50, le=50000)
    max_fragments: int = Field(default=10, ge=1, le=50)
    context_before: int = Field(default=200, ge=0, le=2000)
    context_after: int = Field(default=200, ge=0, le=2000)
    max_merge_gap: int = Field(default=350, ge=0, le=2000)
    min_fragment_size: int = Field(default=40, ge=10, le=1000)


class FragmentSelectionResult(BaseModel):
    """Result of fragment selection containing verifiable references and warnings."""

    model_config = ConfigDict(extra="forbid")

    fragments: list[DocumentFragment] = Field(default_factory=list)
    total_characters: int = 0
    warnings: list[str] = Field(default_factory=list)
    truncated: bool = False
    source_character_count: int = 0


# Detection pattern definitions
_ANNEX_PATTERN = re.compile(
    r"(?i)\b(?:ANEXO|AP[EÉ]NDICE)\s*(?:[Nn][°ºo]\s*)?[\dA-Za-z]+[\s\.\:\-–—]+"
    r".*?(?:CUESTIONARIO|ESCALA|INVENTARIO|GU[IÍ]A|INSTRUMENTO|TEST|PRUEBA)\b[^\n]*",
)

_INSTRUMENT_TITLE_PATTERN = re.compile(
    r"(?i)\b(?:CUESTIONARIO(?:\s+DE\s+[^\n]+)?|"
    r"ESCALA(?:\s+DE\s+[^\n]+|\s+TIPO\s+LIKERT|\s+DE\s+MEDICI[OÓ]N)?|"
    r"INVENTARIO(?:\s+DE\s+[^\n]+)?|"
    r"INSTRUMENTO\s+DE\s+RECOLECCI[OÓ]N(?:\s+DE\s+DATOS)?|"
    r"GU[IÍ]A\s+DE\s+ENTREVISTA|"
    r"FICHA\s+T[EÉ]CNICA\s+DEL\s+INSTRUMENTO|"
    r"TEST\s+PSICOM[EÉ]TRICO)\b",
)

_OPERATIONALIZATION_PATTERN = re.compile(
    r"(?i)\b(?:MATRIZ\s+DE\s+)?OPERACIONALIZACI[OÓ]N\s+(?:DE\s+(?:LAS\s+)?VARIABLES|METODOL[OÓ]GICA)?\b",
)

_NUMBERED_ITEM_PATTERN = re.compile(
    r"(?m)^\s*(?:[IÍ]tem\s*)?(?:\d+|[a-zA-Z]\b)[\.\-\)\:]\s+([A-ZÁÉÍÓÚ¿¡][^\n]{10,})",
)

_DOCX_TABULAR_PATTERN = re.compile(
    r"(?m)^(?:[^\n\t]+\t)+[^\n\t]+$",
)

_DOCX_TABLE_HEADER_KEYWORDS = re.compile(
    r"(?i)\b(?:[IÍ]tem|Pregunta|Reactivo|Enunciado|Afirmaci[oó]n|Alternativas?|Opciones?|"
    r"Totalmente de acuerdo|De acuerdo|En desacuerdo|Totalmente en desacuerdo|"
    r"Siempre|Casi siempre|A veces|Nunca|Dimensiones?|Indicadores?|Escala|Puntuaci[oó]n)\b",
)

_SCALE_OPTIONS_PATTERN = re.compile(
    r"(?i)\b(?:Totalmente de acuerdo|Totalmente en desacuerdo|Muy de acuerdo|Muy en desacuerdo|"
    r"Ni de acuerdo ni en desacuerdo|Siempre|Casi siempre|A veces|Raras veces|Nunca|"
    r"Definitivamente s[ií]|Definitivamente no)\b",
)


def _find_clean_boundary_before(text: str, start: int, max_back: int) -> int:
    """Finds a clean line-break or whitespace boundary backward from start."""
    target = max(0, start - max_back)
    if target == 0:
        return 0
    # Search for nearest newline between target and start
    nl = text.rfind("\n", target, start)
    if nl != -1:
        return nl + 1
    # Fallback to whitespace
    sp = text.rfind(" ", target, start)
    if sp != -1:
        return sp + 1
    return target


def _find_clean_boundary_after(text: str, end: int, max_forward: int) -> int:
    """Finds a clean line-break or whitespace boundary forward up to max_forward."""
    target = min(len(text), end + max_forward)
    if target == len(text):
        return len(text)
    # Search for the cleanest boundary near target
    nl = text.rfind("\n", end, target)
    if nl != -1 and nl > end:
        return nl
    sp = text.rfind(" ", end, target)
    if sp != -1 and sp > end:
        return sp
    return target


def select_instrument_fragments(
    source_text: str,
    limits: FragmentSelectionLimits | None = None,
    document_id: UUID | None = None,
    source_truncated: bool = False,
) -> FragmentSelectionResult:
    """Selects verifiable text fragments containing instrument sections from source text.

    Guarantees:
    - Verifiable offsets: source_text[fragment.start:fragment.end] == fragment.text
    - Deterministic output given the same input and limits.
    - Preserves distinct instruments without arbitrary merging across distant sections.
    - Handles PDF broken lines and DOCX tab-separated tables.
    - Emits actionable warnings on truncation or absence of patterns.
    """
    if limits is None:
        limits = FragmentSelectionLimits()

    source_len = len(source_text)
    if not source_text.strip():
        warnings = ["El texto fuente está vacío."]
        if source_truncated:
            warnings.append(
                "El texto fuente se encuentra truncado y sin contenido disponible para análisis."
            )
        return FragmentSelectionResult(
            fragments=[],
            total_characters=0,
            warnings=warnings,
            truncated=source_truncated,
            source_character_count=source_len,
        )

    raw_candidates: list[tuple[int, int, str]] = []  # (start, end, reason)

    # 1. Detect Annexes
    for match in _ANNEX_PATTERN.finditer(source_text):
        raw_candidates.append((match.start(), match.end(), "Encabezado de anexo de instrumento"))

    # 2. Detect Instrument Titles / Headers
    for match in _INSTRUMENT_TITLE_PATTERN.finditer(source_text):
        raw_candidates.append(
            (match.start(), match.end(), "Título de instrumento o escala de medición")
        )

    # 3. Detect Operationalization Matrix
    for match in _OPERATIONALIZATION_PATTERN.finditer(source_text):
        raw_candidates.append(
            (match.start(), match.end(), "Matriz de operacionalización de variables")
        )

    # 4. Detect DOCX Tabular representations (\t)
    table_lines = list(_DOCX_TABULAR_PATTERN.finditer(source_text))
    t_idx = 0
    while t_idx < len(table_lines):
        m = table_lines[t_idx]
        line = m.group(0)
        if _DOCX_TABLE_HEADER_KEYWORDS.search(line):
            # Identified table header: collect consecutive tabular rows
            table_start = m.start()
            table_end = m.end()
            next_idx = t_idx + 1
            while next_idx < len(table_lines):
                next_m = table_lines[next_idx]
                # If next line is immediately adjacent or separated only by whitespace/newlines
                gap = source_text[table_end : next_m.start()]
                if not gap.strip():
                    table_end = next_m.end()
                    next_idx += 1
                else:
                    break
            raw_candidates.append(
                (
                    table_start,
                    table_end,
                    "Estructura tabular con opciones de respuesta o ítems (DOCX)",
                )
            )
            t_idx = next_idx
        else:
            t_idx += 1

    # 5. Detect Numbered Item Sequences (PDF / DOCX)
    item_matches = list(_NUMBERED_ITEM_PATTERN.finditer(source_text))
    if item_matches:
        # Group contiguous or closely spaced numbered questions
        seq_start = item_matches[0].start()
        seq_end = item_matches[0].end()
        count = 1
        for m in item_matches[1:]:
            if m.start() - seq_end <= 600:
                seq_end = m.end()
                count += 1
            else:
                if count >= 2 or (seq_end - seq_start >= 80):
                    raw_candidates.append(
                        (
                            seq_start,
                            seq_end,
                            f"Secuencia de {count} reactivos o preguntas numeradas",
                        )
                    )
                seq_start = m.start()
                seq_end = m.end()
                count = 1
        if count >= 2 or (seq_end - seq_start >= 80):
            raw_candidates.append(
                (seq_start, seq_end, f"Secuencia de {count} reactivos o preguntas numeradas")
            )

    # 6. Detect response scale option clusters
    for match in _SCALE_OPTIONS_PATTERN.finditer(source_text):
        raw_candidates.append(
            (match.start(), match.end(), "Opciones de escala de respuesta (Likert)")
        )

    if not raw_candidates:
        warnings = []
        if source_truncated:
            warnings.append(
                "El texto fuente se encuentra truncado; no se identificaron patrones en la "
                "porción disponible, pero no se descarta la presencia de instrumentos en las "
                "secciones omitidas."
            )
        else:
            warnings.append(
                "No se identificaron patrones reconocibles de instrumentos de investigación "
                "en el texto analizado."
            )
        return FragmentSelectionResult(
            fragments=[],
            total_characters=0,
            warnings=warnings,
            truncated=source_truncated,
            source_character_count=source_len,
        )

    # Expand contexts around raw candidates
    expanded_windows: list[tuple[int, int, str]] = []
    for c_start, c_end, reason in raw_candidates:
        e_start = _find_clean_boundary_before(source_text, c_start, limits.context_before)
        e_end = _find_clean_boundary_after(source_text, c_end, limits.context_after)
        expanded_windows.append((e_start, e_end, reason))

    # Sort deterministically by start position, then by end position
    expanded_windows.sort(key=lambda w: (w[0], w[1]))

    # Merge overlapping or closely adjacent windows
    merged: list[tuple[int, int, list[str]]] = []
    for w_start, w_end, w_reason in expanded_windows:
        if not merged:
            merged.append((w_start, w_end, [w_reason]))
            continue

        prev_start, prev_end, prev_reasons = merged[-1]

        # If overlapping or gap is within max_merge_gap, merge into a contiguous fragment
        if w_start <= prev_end + limits.max_merge_gap:
            new_end = max(prev_end, w_end)
            if w_reason not in prev_reasons:
                prev_reasons.append(w_reason)
            merged[-1] = (prev_start, new_end, prev_reasons)
        else:
            # Separate distinct instrument region
            merged.append((w_start, w_end, [w_reason]))

    # Apply limits and budget bounds deterministically
    fragments: list[DocumentFragment] = []
    total_chars = 0
    truncated = source_truncated
    warnings: list[str] = []

    if source_truncated:
        warnings.append(
            "El texto fuente se encuentra truncado; la cobertura del instrumento puede "
            "ser parcial y no se descartan secciones adicionales omitidas."
        )

    for m_start, m_end, reasons in merged:
        if len(fragments) >= limits.max_fragments:
            truncated = True
            warnings.append(
                f"Se alcanzó el límite máximo de fragmentos permitidos ({limits.max_fragments}); "
                "algunos fragmentos fueron omitidos."
            )
            break

        frag_len = m_end - m_start
        available = limits.max_total_characters - total_chars

        if available <= 0:
            truncated = True
            warnings.append(
                "Se alcanzó el presupuesto máximo de caracteres para fragmentos documentales; "
                "la extracción cubre únicamente las secciones prioritarias seleccionadas."
            )
            break

        if frag_len > available:
            # Clipped fragment
            if available < limits.min_fragment_size:
                truncated = True
                warnings.append(
                    "Se detuvo la selección de fragmentos por presupuesto insuficiente para "
                    "incluir el siguiente fragmento completo."
                )
                break
            # Find a line break within available space if possible
            clipped_end = m_start + available
            nl = source_text.rfind("\n", m_start, clipped_end)
            if nl != -1 and (nl - m_start) >= limits.min_fragment_size:
                clipped_end = nl

            actual_text = source_text[m_start:clipped_end]
            reasons_str = "; ".join(reasons) + " (truncado por límite de presupuesto)"
            frag = DocumentFragment(
                start=m_start,
                end=clipped_end,
                text=actual_text,
                selection_reason=reasons_str[:300],
                document_id=document_id,
            )
            fragments.append(frag)
            total_chars += len(actual_text)
            truncated = True
            warnings.append(
                "Fragmento truncado para respetar el presupuesto de entrada disponible."
            )
            break
        else:
            actual_text = source_text[m_start:m_end]
            reasons_str = "; ".join(reasons)
            frag = DocumentFragment(
                start=m_start,
                end=m_end,
                text=actual_text,
                selection_reason=reasons_str[:300],
                document_id=document_id,
            )
            fragments.append(frag)
            total_chars += len(actual_text)

    return FragmentSelectionResult(
        fragments=fragments,
        total_characters=total_chars,
        warnings=warnings,
        truncated=truncated,
        source_character_count=source_len,
    )
