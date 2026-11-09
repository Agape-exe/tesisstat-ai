"""Bounded deterministic parser. Never stores/logs the pasted response."""

import json
import re

from pydantic import ValidationError

from app.modules.research.context.import_models import ContextImport
from app.modules.research.context.repository import ContextError


def fail(message: str, fields=None, status=422):
    raise ContextError(
        "invalid_payload" if status == 422 else "limit_exceeded", message, status, fields
    )


def parse_response(text: str) -> tuple[ContextImport, list[str]]:
    if len(text.encode("utf-8")) > 120000:
        fail(
            "La respuesta supera 120 000 bytes. Pide únicamente el resumen estructurado.",
            status=413,
        )
    text = text.strip()
    if text.startswith("```"):
        match = re.fullmatch(r"```(?:json)?\s*\n([\s\S]*?)\n```", text)
        if not match:
            fail("Pide un único bloque JSON, sin introducción ni otros bloques.")
        text = match[1]
    # Bound nesting before decoding, respecting escaped quotes and brackets inside strings.
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > 8:
                fail("La respuesta tiene demasiados niveles (máximo 8).", status=413)
        elif char in "]}":
            depth -= 1

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Hay claves JSON repetidas")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Solo se admiten números finitos")

    try:
        raw = json.loads(text, object_pairs_hook=unique, parse_constant=constant)
    except (ValueError, RecursionError) as exc:
        fail(
            "No se pudo leer un objeto JSON único. Pide al otro chat corregir el formato: "
            + (str(exc)[:150] if not isinstance(exc, RecursionError) else "demasiados niveles")
        )
    if not isinstance(raw, dict):
        fail("Pide un objeto JSON, no una lista ni varios objetos.")
    count = 0

    def bound(value):
        nonlocal count
        count += 1
        if count > 1200:
            fail("La respuesta supera 1200 elementos.", status=413)
        if isinstance(value, str) and len(value) > 2000:
            fail(
                "Un texto supera 2000 caracteres. Pide resumirlo sin perder información.",
                status=413,
            )
        if isinstance(value, dict):
            for k, v in value.items():
                bound(k)
                bound(v)
        elif isinstance(value, list):
            for v in value:
                bound(v)

    bound(raw)
    extra = sorted(set(raw) - ContextImport.model_fields.keys())
    forbidden = {
        "actor",
        "actor_ref",
        "owner_id",
        "approved_at",
        "confirmation",
        "source_refs",
        "project_id",
        "revision",
        "created_at",
        "updated_at",
        "id",
    }
    if forbidden.intersection(extra):
        fail("La respuesta incluye metadatos del servidor. Pide eliminarlos.", extra)
    notes = raw.get("complementary_notes", [])
    if extra and not isinstance(notes, list):
        fail("Las notas complementarias deben ser una lista.", ["complementary_notes"])
    for name in extra:
        rendered = json.dumps(raw.pop(name), ensure_ascii=False, allow_nan=False)
        note = f"Información adicional ({name}): {rendered}"
        if len(note) > 2000 or len(notes) >= 20:
            fail(
                "La información adicional no cabe en 20 notas de 2000 caracteres. "
                "Pide resumirla o revisa la respuesta; no se descartó información.",
                extra,
            )
        notes = [*notes, note]
    if extra:
        raw["complementary_notes"] = notes
    try:
        return ContextImport.model_validate(raw), extra
    except ValidationError as exc:
        fields = ["/" + "/".join(map(str, e["loc"])) for e in exc.errors()]
        details = "; ".join(e["msg"] for e in exc.errors())[:800]
        fail("Pide corregir los campos indicados según el prompt. " + details, fields)


def candidates(proposal: ContextImport) -> dict[str, object]:
    result = {}
    for name in (
        "research_question",
        "main_objective",
        "study_description",
        "data_description",
        "observational_unit",
        "sampling_notes",
        "design",
        "observations",
    ):
        value = getattr(proposal, name)
        if value not in (None, "", "unknown"):
            result[name] = value
    for name in ("specific_objectives", "hypotheses"):
        for item in getattr(proposal, name):
            result[f"{name}/{item.ref}"] = item
    for i, note in enumerate(proposal.complementary_notes):
        result[f"complementary_notes/{i}"] = note
    return result
