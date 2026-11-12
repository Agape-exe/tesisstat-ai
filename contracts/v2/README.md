# Familia v2: contexto, fuentes e intención/snapshot

S06 concreta C7 y la presentación C5 con `TutorContextV2`, `MessageDraftV2`,
`TutorSelectionV2`, `TutorConsentV2`, `ResultExplanationV2`, `ExplanationReviewV2`,
`ResultPresentationV2` y `ResultFiguresV2`. Canónicos en `shared/tutor_v2.py` y
`shared/reports_v2.py`; mismos generadores, sin editar schemas/tipos a mano.
Las interpretaciones IA se guardan separadas del resultado numérico y conservan revisión.
El consentimiento `tutor_context_v3` es distinto del anterior `research_context_v2`.
Detalle ejecutable y límites: [C5/C7](../../docs/CONTRATOS_EVOLUCION.md#implementación-s06-de-c5-y-c7)
y [evidencia S06](../../docs/sesiones/S06.md).

S05 incorpora C6: InstrumentContextV2, InstrumentMappingV2, ScorePreviewV2,
ScoreRecordV2 y ScoreDerivedTableV2, con DTOs de edición/confirmación separados. Canónicos
en `shared/instruments_v2.py`; los diez ejemplos C6 proceden del recorrido sintético real
de S05 y se validan con modelos y JSON Schema en `test_instruments_v2_contracts.py`.
No son datos semilla ni documentos metodológicos ficticios.
Fuente/puerto y revisión: [API C6](../../backend/app/modules/research/instrument/README.md).
Alfa usa `cronbach-alpha-recoded-v2`; los controles de aprobación y ejecución son los C5.
Se mantienen esquemas/tipos/ejemplos v1. Los campos C6 opcionales ausentes no cambian
hashes/tokens de snapshots S04B; SourceRef añade `recoding` como dependencia explícita.

S04A habilita intenciones y diagnósticos: `DiagnosticV2`, `IntentPatch`, `DiagnosticRequest`
y extensiones opcionales de AnalysisIntentV2 para tabla/unidad/identificación/vínculo.
Canónicos en `shared/diagnostics_v2.py` y `research/intents/models.py`, generados por los
mismos scripts. [API y garantías](../../backend/app/modules/research/intents/README.md).
S04B incorporó snapshots/propuestas/aprobación/ejecución v2; S05 completa confiabilidad
sobre esos mismos controles.

S02B añade `ContextImport`, `ContextSuggestion`, `SuggestionCreate` y `SuggestionApply`,
canónicos en `research/context/import_models.py`. El formato externo context-import-1.0
no es un DTO de Facts persistidos: referencias locales se traducen a UUIDs por el servidor,
procedencia/confirmaciones no se toman del chat. Esquemas/tipos se generan con los comandos
existentes. [Semántica C2 y límites](../../docs/CONTRATOS_EVOLUCION.md#s02b--contrato-ejecutable-de-importación-asistida).

Canónicos: `backend/app/shared/analysis_v2.py` y `data_sources_v2.py` y `data_workspace_v2.py`. S02 habilita C2;
S03A habilita archivos, hojas, tablas y contexto C3; S03B diccionario, perfil y derivados.
C4 conserva su estructura preparada para S04.
Los seis contratos v1 y sus ejemplos permanecen intactos.

Corrección de alcance S02B: `ProjectContextV2.observational_unit` es la entidad general
estudiada (opcional); `TableContextV2.row_meaning` describe filas de UNA tabla. No se copian
automáticamente. `ProjectContextV2.observations` es antecedente legado, con su procedencia,
confirmación e historial intactos. Las intenciones S04 deben resolver sus relaciones y
comparaciones propias; no heredan esa confirmación ni aprueban unilateralidad desde C2.
Enums/formatos guardados se mantienen compatibles; cambios de esquema documentan semántica.
Prompt `context-prompt-1.1` solicita observations=unknown; importador anterior 1.0 compatible
propone notas para clasificaciones antiguas y bloquea aplicarlas globalmente.

Desde backend: `python -m scripts.export_contracts` regenera ambas familias;
`--check` comprueba actualidad. Desde frontend: `npm run contracts:generate` genera tipos
v1 y subcarpeta `generated/v2`. No editar los JSON Schema ni TypeScript generados a mano.
Schema `2.0.0`, revisión de recurso y versión de algoritmo son conceptos separados.

`python -m scripts.export_v2_examples` regenera ejemplos deterministas sintéticos. Los ejemplos
de C4 solo validan la estructura: sus fuentes están declaradas en `examples/sources.json`,
con un CSV ficticio verificable. Son fixtures estáticos; no se insertan en la aplicación,
no son recursos operativos C3 ni acreditan perfil, diagnóstico o ejecución real. El test
verifica pertenencia, revisiones, hashes y conteos del CSV. No hay materialización de
snapshots durante la creación de proyectos o guardado de contexto.

Decisiones compatibles de S02 y consumidores:

- `AnalysisIntentV2.observations` es Fact del enum C2: explicita la procedencia y confirmación
  exigidas por C4. S04/Orchestration consumirá `.value`; no inferir independencia por defecto.
- `Provenance.algorithm_version` opcional hace verificable la regla derived requiere
  fuente/algoritmo. Obligatorio solo cuando kind=derived; S03/S04 lo completarán.
- SourceRef de contexto usa `id=project_id` porque C2 no tiene un ID distinto. La revisión
  identifica el histórico. UI y futuro resolver deben usar esa identidad canónica.
- `SnapshotVariableV2` es proyección de variables elegidas (id, columnas, nombre y escala),
  no un diccionario editable completo. S03B prepara el recurso de diccionario y S04 construye
  esta proyección al resolver las fuentes. No se habilitan endpoints C3 en S02.
- `source_refs` enumera las referencias nombradas del snapshot. El validador verifica tipo,
  pertenencia a esa lista, revisión/hash de intención congelada y variables seleccionadas.
  Resolver otras fuentes/columnas y permisos sigue siendo responsabilidad del servidor S04.
- `canonical_hash` implementa json-sort-v1; excluye fechas, confirmaciones y hash propio del
  recurso editable. Conserva hashes anidados de SourceRef. DatasetRefV2 de tablas usa
  table-json-v1 según la adaptación S03B; los datasets v1 conservan research-dataset-v1.

No hay lectura heurística de v2 por consumidores v1 ni reutilización de aprobaciones.

## Fuentes C3 de S03A

`SourceFileV2` agrupa `SourceSheetV2`; cada hoja lista apunta a `ImportedTableV2`, con
original_hash, extracción, columnas UUID y content_hash independiente de `TableContextV2`.
`TablePreviewV2` contiene una ventana de esa misma extracción; no materializa otra tabla.
Desde C01 las nuevas importaciones XLSX calculan el subconjunto `excel-subset-1`, ignoran
la caché y conservan fórmula/procedencia/errores. Los históricos mantienen su política;
los faltantes se conservan y ninguna fila llega al proveedor IA. Véase
[el contrato de cálculo](../../backend/app/modules/research/sources/README.md#c01-cálculo-local-y-reimportación).

`python -m scripts.export_source_examples` regenera los cinco ejemplos C3 y el CSV real
enlazado; tests verifican modelos/esquemas y hashes/conteos/referencias con sus bytes.
`python -m scripts.create_s03a_examples` regenera el Excel multihoja y CSV de demostración
en `fixtures/data/s03a`. No se insertan recursos ficticios al abrir proyectos anteriores.

El enum SourceRef v2 añade `source_file|source_sheet|table|table_context`.
`SourceService.source_refs` los resuelve en servidor; contexto usa id=table_id y su propia
revisión. La futura construcción de AnalysisSnapshot adaptará esta evidencia C3 a su
dataset/diccionario elegido; no hay consumidor ejecutable nuevo en esta entrega.
Lectura completa, límites, selección y recuperación:
[API C3](../../backend/app/modules/research/sources/README.md).

## Diccionario, perfil y derivados S03B

`DatasetRefV2` identifica tabla JSON importada/derivada con hash table-json-v1. Nunca es un
CSV/XLSX ficticio. `VariableDictionaryV2` guarda facts, listas, vínculos escalares e históricos.
`TableProfileV2` guarda evidencia completa, política/versiones y vigencia. `TableRecipeV2`,
`PreparationPreviewV2` y `DerivedTableV2` conservan recetas, todas las fuentes, linaje y
confirmación humana. No se heredan confirmaciones al derivar ni se materializa un snapshot
C4 automáticamente. `preparation` en SourceRef referencia el hash canónico de la receta.

`python -m scripts.export_workspace_examples` genera ejemplos deterministas ejecutando los
servicios reales sobre el CSV sintético ya existente. Tests validan esquema/ejemplo, y los
conteos/filas de combinación se contrastan con resultados esperados escritos a mano en
`test_data_workspace_v2.py`, independientes del algoritmo productivo.
Puerto completo, operaciones PATCH, hashes/políticas y límites exactos:
[API S03B](../../backend/app/modules/research/data_workspace/README.md).
