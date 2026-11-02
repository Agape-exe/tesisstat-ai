"""Explicit Spanish rules. User text never authorizes an operation."""

import re

from app.modules.conversation.context import normalize
from app.modules.conversation.models import Message
from app.orchestration.multiagent.state import RequestType


def classify(content: str, history: list[Message]) -> RequestType:
    query = normalize(content)
    if re.search(
        r"\b(ejecut\w*|calcul\w*|apru[eé]b\w*|aprobar|modific\w*|cambi\w*|"
        r"borr\w*|elimin\w*|corre|correr|aplica\w*)\b",
        query,
    ):
        return "blocked_execution"
    # General definitions must not accidentally trigger project tools.
    definition = bool(re.search(r"\b(que es|que son|define|definicion|concepto)\b", query))
    project = bool(re.search(r"\b(mi|mis|nuestro|nuestra|proyecto|tesis|investigacion)\b", query))
    if definition and not re.search(r"\b(mi|mis|nuestro|nuestra|proyecto|tesis)\b", query):
        return "general"
    if re.search(r"resultado|p.valor|significancia|coeficiente|historico|anterior", query):
        return "results"
    if re.search(r"analisis|estadistic|prueba|pearson|spearman|anova|planific|tecnica", query):
        return "planning"
    if re.search(r"dataset|\bdatos\b|columna|\bfila|\beda\b|preparacion|faltante|duplicad", query):
        return "data"
    if re.search(
        r"metod|objetiv|hipotes|variable|dimension|escala|diseno|muestra|poblacion", query
    ):
        return "methodology"
    # Only short anaphoric follow-ups inherit the last actually executed route.
    if re.search(r"^(¿?y\b|¿?por que\b|explica|esa |ese |la primera|la segunda)", query):
        previous = next((m for m in reversed(history) if m.role == "assistant"), None)
        route = (
            (previous.context or {}).get("multiagent", {}).get("request_type") if previous else None
        )
        if route in {"methodology", "data", "results", "planning"}:
            return route
    if re.search(r"\b(hola|gracias|buenos dias|buenas tardes|buenas noches)\b", query):
        return "general"
    return "methodology" if project else "clarification"
