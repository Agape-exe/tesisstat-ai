"""Closed procedural guidance; the model cannot infer a design by comparing values."""

from app.shared.ai_errors import AIError


def variables(context):
    return [v for v in context.data_summary if v.get("variable") and not v.get("identifier")]


def option_indices(context):
    columns = variables(context)
    quantitative = [
        v
        for v in columns
        if v.get("detected_type") == "numérico"
        and not (v.get("scale_confirmed") and v.get("scale") == "nominal")
    ]
    result = []
    for index, action in enumerate(context.allowed_actions):
        if action.kind == "start_association" and len(quantitative) < 2:
            continue
        if action.kind == "start_comparison" and (not quantitative or len(columns) < 2):
            continue
        if action.destination == "instrument" and not context.intent_summary.get(
            "instrument_state"
        ):
            continue
        result.append(index)
    return result


def next_steps(context):
    columns = variables(context)
    steps = []
    if columns:
        if not context.intent_summary.get("observations_confirmed"):
            steps.append("clarify_observations")
        if any(not v.get("meaning_confirmed") or not v.get("scale_confirmed") for v in columns):
            steps.append("review_variables")
        if any(v.get("missing") or v.get("formula_errors") or v.get("constant") for v in columns):
            steps.append("review_quality")
        if not steps:
            steps.append("review_variables")
    if context.intent_summary.get("id"):
        steps.append("review_analysis")
    if context.intent_summary.get("result_status"):
        steps.append("review_result")
    return steps or ["select_data"]


def render_step(kind, context):
    if kind not in next_steps(context):
        raise AIError("invalid_response")
    columns = variables(context)
    pending = [v for v in columns if not v.get("meaning_confirmed") or not v.get("scale_confirmed")]
    names = " y ".join(f"«{v['name']}»" for v in (pending or columns)[:2]) or "las medidas"
    row_known = any(f.context_field == "/table/row_meaning" for f in context.evidence)
    return {
        "clarify_observations": (
            "Primero aclararía cómo se vinculan las mediciones entre sí."
            if row_known
            else "Primero aclararía qué representa cada fila y cómo se vinculan "
            "las mediciones entre sí."
        )
        + " Ese vínculo debe declararse; no se determina por similitud de valores "
        "ni por orden de filas.",
        "review_variables": f"Empezaría revisando el significado y la escala de {names} "
        "antes de elegir los resúmenes o comparaciones.",
        "review_quality": "Empezaría revisando los faltantes, errores o variables sin variación "
        "señalados por la comprobación local, sin eliminar ni modificar registros automáticamente.",
        "review_analysis": "Primero revisaría la intención seleccionada y las aclaraciones "
        "necesarias antes de solicitar su propuesta.",
        "review_result": "Primero revisaría el resultado guardado, sus casos utilizados y "
        "su vigencia antes de interpretarlo.",
        "select_data": "Primero cargaría o seleccionaría la tabla pertinente para orientar "
        "la revisión desde sus variables.",
    }[kind]


def render_options(indices, context):
    allowed = option_indices(context)
    if any(index not in allowed for index in indices):
        raise AIError("invalid_response")
    labels = {
        "prepare_descriptive": "Podrías comenzar por describir las medidas con resúmenes "
        "acordes con su significado y escala.",
        "start_association": "También podrías explorar relaciones entre medidas si corresponde "
        "vincularlas por sus unidades de observación.",
        "start_comparison": "Para comparar grupos o mediciones habría que aclarar su diseño "
        "y si corresponden a las mismas unidades o a unidades distintas.",
        "request_diagnostic": "Podrías revisar los diagnósticos de la intención seleccionada.",
        "request_proposal": "Con las aclaraciones necesarias, podrías abrir la revisión de "
        "una propuesta; aprobarla y ejecutarla seguirían siendo acciones separadas.",
    }
    destinations = {
        "datasets": "la tabla y sus variables",
        "context": "el contexto opcional",
        "analysis": "la intención de análisis",
        "results": "los resultados guardados",
        "instrument": "el instrumento y sus reglas",
        "home": "el inicio del proyecto",
    }
    return " ".join(
        labels.get(
            context.allowed_actions[i].kind,
            "Podrías revisar " + destinations[context.allowed_actions[i].destination] + ".",
        )
        for i in dict.fromkeys(indices)
    )
