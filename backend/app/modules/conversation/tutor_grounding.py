"""Separate general prose from a closed, evidence-typed language for study findings.

There is no provider-written result prose. The scope guard is defense in depth for
general conversation, not a proof that an LLM's teaching is scientifically correct.
"""

import re

from app.modules.conversation.tutor_privacy import normalize
from app.modules.statistics.presentation_v2 import format_number, metric_label, metric_unit
from app.shared.ai_errors import AIError


def validate_general_prose(text, *, example=False):
    """Reject empirical predicates in the general lane, not numbers or statistical terms.

    Check subject/predicate scope, rather than treating a metric reference as permission
    for all sentences. Quantities in definitions and explicitly hypothetical examples are
    allowed. Study findings have to use render_findings below, even without digits.
    """
    # A complete clarification asks about an unknown; it does not assert a finding.
    # Assertions outside interrogative spans still pass every empirical guard below.
    value = re.sub(r"¿[^¿?]+\?", "", normalize(text))
    empirical = (
        r"\b(?:se\s+(?:(?:ha|han)\s+)?|hemos\s+|has\s+)"
        r"(?:demostrad[oa]|demuestra|demuestran|observad[oa]|observo|observa|encontrad[oa]|"
        r"encontro|detectad[oa]|detecto|comprobad[oa]|comprobo|obtenid[oa]|obtuvo)\b"
    )
    for sentence in re.split(r"[;!?\n]|(?<!\d)\.(?!\d)", value):
        for match in re.finditer(empirical, sentence):
            # A general caution such as 'no se ha demostrado causalidad' isn't a finding.
            if not re.search(r"\b(?:no|nunca|ni)\s+(?:\w+\s+){0,2}$", sentence[: match.start()]):
                return False
        subject = (
            r"\b(?:mi|mis|tu|tus|su|sus|nuestr[oa]s?|est[ea]s?|el|la|los|las)\s+"
            r"(?:muestra|estudio|investigacion|analisis|datos|resultados|pacientes|"
            r"participantes|sujetos|casos|tabla|tablas|columna|columnas|variables)\b"
        )
        for subject_match in re.finditer(subject, sentence):
            if re.match(
                r"\s+(?:(?:ya|tambien|solo|claramente|estadisticamente|son|es|estan|esta)\s+){0,3}"
                r"(?:tiene|tienen|hay|incluye|incluyen|contiene|contienen|participaron|"
                r"fue|fueron|eran|mostro|muestra|presenta|presentan|demuestra|confirma|"
                r"significativ[oa]s?|causalidad|causal|positiv[oa]|negativ[oa]|"
                r"numeric[oa]s?|normal(?:es)?|independientes?|paread[oa]s?)\b",
                sentence[subject_match.end() :],
            ):
                return False
        if re.search(
            r"\b(?:el|la)\s+(?:correlacion|coeficiente|valor\s+p|diferencia|alfa)\s+"
            r"(?:es|fue|resulta|resulto)\s+(?:positiv[oa]|negativ[oa]|significativ[oa]|\d)",
            sentence,
        ):
            return False
        if not example and (
            re.search(r"\b(?:p|r|rho|alfa|alpha|n)\s*(?:=|<|>)\s*\d", sentence)
            or re.search(
                r"\b(?:hay|hubo|incluye|incluyeron|participaron|tenemos)\s+"
                r"(?:\w+\s+|\d+\s+){0,4}(?:pacientes|participantes|personas|casos)\b",
                sentence,
            )
        ):
            return False
    return True


def prose_without_facts(text):
    return re.sub(r"\{\{f\d+\}\}", "", text).strip()


def render_contextual_prose(text, evidence):
    """Validate prose BEFORE inserting server facts, never grant a whole paragraph a citation."""
    by_key = {f.key: f for f in evidence}
    keys = re.findall(r"\{\{(f\d+)\}\}", text)
    for match in re.finditer(r"\{\{f\d+\}\}", text):
        prefix = text[: match.start()].rstrip()
        if prefix and not (prefix[-1] in ".!?;:" or prefix.endswith("}}")):
            # A fact is a complete server sentence, never a variable-name substitution.
            raise AIError("invalid_response")
    plain = prose_without_facts(text)
    if "{{" in plain or "}}" in plain or any(key not in by_key for key in keys):
        raise AIError("invalid_response")
    if not validate_general_prose(plain):
        raise AIError("invalid_response")
    rendered = re.sub(r"\{\{(f\d+)\}\}", lambda m: by_key[m[1]].text, text)
    return rendered, list(dict.fromkeys(keys))


def render_findings(findings, metric_map, result):
    """Only server-owned templates can make assertions about a selected result."""
    if findings and (not result or result.status != "completed"):
        raise AIError("invalid_response")
    lines, keys = [], []
    for finding in findings:
        if finding.kind == "case_counts":
            if finding.metric_key is not None:
                raise AIError("invalid_response")
            counts = result.case_counts
            lines.append(
                f"Casos guardados: {counts.total} totales, {counts.used} utilizados, "
                f"{counts.excluded} excluidos."
                + (f" Pares completos: {counts.pairs}." if counts.pairs is not None else "")
            )
            continue
        metric = metric_map.get(finding.metric_key)
        if metric is None:
            raise AIError("invalid_response")
        suffix = metric.key.rsplit(".", 1)[-1]
        if finding.kind == "association_direction" and (
            result.technique not in {"pearson", "spearman"}
            or suffix not in {"r", "rho"}
            or metric.value is None
        ):
            raise AIError("invalid_response")
        if finding.kind == "p_value" and (suffix != "p_value" or metric.value is None):
            raise AIError("invalid_response")
        keys.append(metric.key)
        line = (
            f"{metric_label(metric)}: {format_number(metric.value, metric.key)}"
            + (f" {metric_unit(metric)}" if metric_unit(metric) else "")
            + "."
        )
        if finding.kind == "association_direction":
            direction = (
                "positivo" if metric.value > 0 else "negativo" if metric.value < 0 else "cero"
            )
            line += f" El coeficiente guardado es {direction}; no demuestra causalidad."
        if finding.kind == "p_value":
            line += (
                " Se reproduce el valor p, sin afirmar significación bajo un umbral no guardado."
                " No determina relevancia práctica ni causalidad."
            )
        lines.append(line)
    return "\n".join(dict.fromkeys(lines)), list(dict.fromkeys(keys))
