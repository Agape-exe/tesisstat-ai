"""Tests for document fragment selection of research instruments.

Verifies:
1. Questionnaire with explicit heading.
2. Questionnaire inside an annex/appendix.
3. DOCX table represented with tab separators (\\t).
4. Numbered consecutive questions without explicit header.
5. Document with multiple separate instruments.
6. Long document with extensive irrelevant introductory content.
7. Document without recognizable instrument patterns.
8. Truncated text with incomplete coverage warning.
9. Overlapping and closely adjacent fragments merged into contiguous window.
10. Insufficient budget truncation.
11. Verifiable exact offsets: source_text[start:end] == fragment.text.
12. Deterministic selection and repeatable results.
"""

from __future__ import annotations

from uuid import uuid4

from app.modules.research.instrument.fragment_selector import (
    FragmentSelectionLimits,
    select_instrument_fragments,
)


def test_1_questionnaire_with_explicit_heading():
    """1. Cuestionario con encabezado explícito: detecta título y reactivos."""
    text = (
        "El presente estudio evalúa las competencias.\n\n"
        "CUESTIONARIO DE COMPETENCIAS DIGITALES\n"
        "Instrucciones: Responda a cada afirmación según su nivel de acuerdo.\n"
        "1. Utilizo herramientas en la nube para gestionar información académica.\n"
        "2. Comparto recursos educativos abiertos mediante plataformas virtuales.\n"
        "3. Aplico criterios de seguridad digital al navegar en la red.\n\n"
        "Fin del instrumento."
    )
    result = select_instrument_fragments(text)

    assert len(result.fragments) >= 1
    frag = result.fragments[0]
    assert "CUESTIONARIO DE COMPETENCIAS DIGITALES" in frag.text
    assert "1. Utilizo herramientas" in frag.text
    # Verificación de fidelidad de offsets
    assert text[frag.start : frag.end] == frag.text


def test_2_questionnaire_inside_annex():
    """2. Cuestionario dentro de un anexo: detecta encabezado de anexo."""
    text = (
        "Capítulo IV: Resultados y Discusión.\n"
        "Los datos fueron recolectados en el periodo 2026.\n\n"
        "ANEXO 1: CUESTIONARIO DE CLIMA ORGANIZACIONAL\n"
        "Dirigido a los colaboradores de la institución.\n"
        "1. Mi jefe inmediato reconoce mi esfuerzo y aportes laborales.\n"
        "2. Existen canales de comunicación abiertos entre las áreas.\n"
    )
    result = select_instrument_fragments(text)

    assert len(result.fragments) == 1
    frag = result.fragments[0]
    assert "ANEXO 1" in frag.text
    assert "CUESTIONARIO DE CLIMA ORGANIZACIONAL" in frag.text
    assert "Encabezado de anexo de instrumento" in frag.selection_reason
    assert text[frag.start : frag.end] == frag.text


def test_3_docx_table_with_tabs():
    """3. Tabla DOCX representada mediante tabulaciones (\\t)."""
    text = (
        "A continuación se presenta la matriz de recolección:\n\n"
        "N°\tÍtem\tTotalmente de acuerdo\tDe acuerdo\tEn desacuerdo\tTotalmente en desacuerdo\n"
        "1\tLa institución brinda capacitación continua.\t4\t3\t2\t1\n"
        "2\tCuento con los recursos tecnológicos necesarios.\t4\t3\t2\t1\n"
        "3\tExiste equilibrio entre vida laboral y familiar.\t4\t3\t2\t1\n\n"
        "Nota: Los datos serán confidenciales."
    )
    result = select_instrument_fragments(text)

    assert len(result.fragments) >= 1
    frag = result.fragments[0]
    assert "\t" in frag.text
    assert "Totalmente de acuerdo" in frag.text
    assert "La institución brinda capacitación continua." in frag.text
    assert text[frag.start : frag.end] == frag.text


def test_4_consecutive_numbered_questions():
    """4. Preguntas numeradas consecutivas sin título de cuestionario previo."""
    text = (
        "Sección de consulta ciudadana:\n\n"
        "1. ¿Cómo califica la atención recibida en el centro de salud?\n"
        "2. ¿El tiempo de espera fue razonable durante su consulta?\n"
        "3. ¿El personal médico resolvió con claridad sus inquietudes?\n"
        "4. ¿Recomendaría este servicio a familiares y amigos?\n\n"
        "Agradecemos su valiosa participación."
    )
    result = select_instrument_fragments(text)

    assert len(result.fragments) >= 1
    frag = result.fragments[0]
    assert "1. ¿Cómo califica" in frag.text
    assert "4. ¿Recomendaría" in frag.text
    assert text[frag.start : frag.end] == frag.text


def test_5_multiple_distinct_instruments():
    """5. Documento con varios instrumentos: conserva fragmentos separados sin mezclarlos."""
    instrument_1 = (
        "ANEXO A: ESCALA DE MOTIVACIÓN INTRÍNSECA\n"
        "1. Disfruto aprender nuevos conceptos cada día.\n"
        "2. Me esfuerzo por superar mis metas personales.\n"
    )
    filler = (
        "\n"
        + ("Este es un texto intermedio de separación que no contiene preguntas ni tablas.\n" * 40)
        + "\n"
    )
    instrument_2 = (
        "ANEXO B: INVENTARIO DE BURNOUT ACADÉMICO\n"
        "1. Me siento agotado al finalizar la jornada de estudio.\n"
        "2. Siento que las exigencias académicas superan mi energía.\n"
    )
    full_text = f"{instrument_1}{filler}{instrument_2}"

    result = select_instrument_fragments(
        full_text,
        limits=FragmentSelectionLimits(max_merge_gap=200, context_before=50, context_after=50),
    )

    assert len(result.fragments) == 2
    # El primer fragmento debe pertenecer a la Escala A
    assert "ESCALA DE MOTIVACIÓN INTRÍNSECA" in result.fragments[0].text
    assert "INVENTARIO DE BURNOUT" not in result.fragments[0].text

    # El segundo fragmento debe pertenecer al Inventario B
    assert "INVENTARIO DE BURNOUT ACADÉMICO" in result.fragments[1].text
    assert "MOTIVACIÓN INTRÍNSECA" not in result.fragments[1].text

    # Ambos verifican offsets exactos
    for frag in result.fragments:
        assert full_text[frag.start : frag.end] == frag.text


def test_6_long_document_with_irrelevant_information():
    """6. Documento largo con información irrelevante: extrae únicamente el fragmento relevante."""
    irrelevant_intro = "Marco Teórico y Estado del Arte.\n" + (
        "Párrafo extenso sin instrumentos.\n" * 150
    )
    instrument_section = (
        "ESCALA DE AUTOEFICACIA DOCENTE\n"
        "1. Puedo adaptar mi metodología a las necesidades de los alumnos.\n"
        "2. Logro mantener el interés del aula ante temas complejos.\n"
        "3. Utilizo evaluaciones formativas de manera regular.\n"
    )
    irrelevant_outro = "Referencias Bibliográficas:\n" + (
        "Autor, A. (2020). Título de la obra.\n" * 80
    )

    full_text = f"{irrelevant_intro}\n\n{instrument_section}\n\n{irrelevant_outro}"

    result = select_instrument_fragments(full_text)

    assert len(result.fragments) == 1
    frag = result.fragments[0]
    assert "ESCALA DE AUTOEFICACIA DOCENTE" in frag.text
    # El tamaño del fragmento seleccionado es acotado y no contiene todo el documento
    assert len(frag.text) < len(full_text) * 0.3
    assert full_text[frag.start : frag.end] == frag.text


def test_7_document_without_recognizable_patterns():
    """7. Documento sin patrones reconocibles: lista vacía con advertencia."""
    text = (
        "Capítulo II: Revisión de la Literatura.\n"
        "Los antecedentes históricos de la educación superior en América Latina se remontan\n"
        "a la fundación de la Real y Pontificia Universidad en el siglo XVI.\n"
        "Diversos autores coinciden en la influencia del modelo colonial."
    )
    result = select_instrument_fragments(text)

    assert len(result.fragments) == 0
    assert result.truncated is False
    assert len(result.warnings) == 1
    assert "No se identificaron patrones" in result.warnings[0]


def test_8_truncated_source_text():
    """8. Texto truncado: conserva advertencia sin negar existencia categóricamente."""
    truncated_text = (
        "Capítulo III: Metodología.\n"
        "Para la recolección de datos se aplicó un cuestionario estructurado en...\n"
        "[TEXTO CORTADO POR LÍMITE DE PÁGINAS]"
    )
    result = select_instrument_fragments(truncated_text, source_truncated=True)

    assert result.truncated is True
    # No afirma categóricamente que no existan instrumentos
    assert any("texto fuente se encuentra truncado" in w for w in result.warnings)
    assert not any("Se confirma que no existen instrumentos" in w for w in result.warnings)


def test_9_overlapping_fragments_merge():
    """9. Fragmentos solapados: combina regiones adyacentes sin duplicación."""
    text = (
        "ANEXO 1: CUESTIONARIO DE DESEMPEÑO DOCENTE\n"
        "Escala tipo Likert:\n"
        "1 = Totalmente en desacuerdo, 2 = En desacuerdo, 3 = De acuerdo, 4 = Muy de acuerdo\n"
        "1. El profesor explica con claridad los temas del curso.\n"
        "2. Las actividades prácticas refuerzan los conceptos teóricos.\n"
    )
    result = select_instrument_fragments(text, limits=FragmentSelectionLimits(max_merge_gap=400))

    # El encabezado, la escala Likert y los ítems deben fusionarse en un solo fragmento continuo
    assert len(result.fragments) == 1
    frag = result.fragments[0]
    assert "ANEXO 1" in frag.text
    assert "Totalmente de acuerdo" in frag.text
    assert "1. El profesor explica" in frag.text
    assert text[frag.start : frag.end] == frag.text


def test_10_insufficient_budget():
    """10. Presupuesto insuficiente: detiene o trunca y emite advertencia explícita."""
    text = (
        "CUESTIONARIO DE PRUEBA EXCLUSIVA\n"
        "1. Primera pregunta con texto descriptivo suficiente.\n"
        "2. Segunda pregunta con texto adicional para consumir presupuesto.\n"
        "3. Tercera pregunta que excede el límite máximo de caracteres.\n"
    )
    # Límite muy restrictivo: solo 100 caracteres
    limits = FragmentSelectionLimits(max_total_characters=100, min_fragment_size=30)
    result = select_instrument_fragments(text, limits=limits)

    assert result.truncated is True
    assert result.total_characters <= 100
    assert any("presupuesto" in w or "truncado" in w for w in result.warnings)
    for frag in result.fragments:
        assert text[frag.start : frag.end] == frag.text


def test_11_verifiable_offsets_exact_match():
    """11. Offsets verificables: cumple estrictamente source_text[start:end] == fragment.text."""
    text = (
        "Prefacio del documento.\n\n"
        "MATRIZ DE OPERACIONALIZACIÓN DE VARIABLES\n"
        "Variable\tDefinición\tDimensiones\tIndicadores\tÍtems\n"
        "Clima\tPercepción global\tLiderazgo\tApoyo\t1, 2, 3\n\n"
        "CUESTIONARIO DE CLIMA LABORAL\n"
        "1. Percibo apoyo de mi supervisor directo.\n"
        "2. El liderazgo en la empresa fomenta la colaboración.\n"
    )
    doc_id = uuid4()
    result = select_instrument_fragments(text, document_id=doc_id)

    assert len(result.fragments) >= 1
    for frag in result.fragments:
        assert frag.document_id == doc_id
        # Garantía contractual estricta
        assert text[frag.start : frag.end] == frag.text
        assert frag.end > frag.start
        assert len(frag.text) == (frag.end - frag.start)


def test_12_deterministic_selection():
    """12. Selección determinista: ejecuciones repetidas producen idénticos resultados."""
    text = (
        "ANEXO 2: INVENTARIO DE HÁBITOS DE ESTUDIO\n"
        "1. Planifico un horario fijo para estudiar.\n"
        "2. Tomo notas organizadas durante las clases virtuales.\n"
        "3. Reviso mis apuntes antes de cada evaluación.\n"
    )
    limits = FragmentSelectionLimits()

    res1 = select_instrument_fragments(text, limits=limits)
    res2 = select_instrument_fragments(text, limits=limits)

    assert len(res1.fragments) == len(res2.fragments)
    for f1, f2 in zip(res1.fragments, res2.fragments, strict=True):
        assert f1.start == f2.start
        assert f1.end == f2.end
        assert f1.text == f2.text
        assert f1.selection_reason == f2.selection_reason
    assert res1.total_characters == res2.total_characters
    assert res1.warnings == res2.warnings
    assert res1.truncated == res2.truncated
