# InstrumentContext v1 0 0

## Propósito

`InstrumentContext v1.0.0` es el contrato independiente por el que Research entrega a
Statistics la definición confirmada de un instrumento y, opcionalmente, su mapeo vigente a un
dataset. No sustituye ni cambia `ResearchPackage`, `ResearchVariable`, `DatasetReference`,
`AnalysisPlan` o `AnalysisResult` v1.0.0.

Research es propietario de la extracción, edición humana, persistencia, versionado, vinculación
con columnas y creación de datasets derivados. Statistics consume un contexto confirmado por un
puerto de lectura `InstrumentContextReader.get_confirmed_context(project_id, instrument_id)`; no
importa repositorios ni servicios internos de Research. El protocolo pertenece al contrato de
intercambio y su adaptador será implementado por Research. La composición deberá verificar
propiedad y autorización antes de resolverlo.

## DTO canónico

La implementación Pydantic está en `backend/app/shared/instrument_context.py`. Produce el esquema
JSON mediante `InstrumentContext.model_json_schema()` y es el DTO de intercambio para esta fase.
No se ha añadido al exportador de los contratos compartidos: esa publicación se hará al mismo
tiempo que Research implemente su adaptador y sus rutas.

El DTO contiene:

- Identidad: `instrument_id`, `project_id`, `research_package_id` opcional, `version` y estado.
- Trazabilidad: `methodology_review_id` almacena el `document_id` UUID de la revisión
  metodológica actual, acompañado de proyecto, versión, hash, documento opcional, fechas y
  confirmación humana con referencia opaca al confirmante.
- Matriz verificable: `variable_id` -> `dimension_id` -> `indicator_id` -> `item_id`.
- Ítems: texto, tipo de respuesta, opciones/códigos, valores numéricos, rango, inversión y
  procedencia.
- Reglas confirmadas de suma o promedio y la única política inicial de faltantes:
  `all_required`.
- Mapeo opcional a dataset: ID, hash, versión del instrumento y `item_id` ->
  `column_name`.

Nunca incluye filas, respuestas individuales, rutas de almacenamiento ni secretos.

## Estados y confirmación

Un contexto puede estar en `draft`, `reviewed` o `stale`. Solo `reviewed` exige confirmación
humana del contexto y de todas sus reglas de puntuación. Un instrumento puede estar `reviewed`
sin `dataset_mapping`. Un mapeo `confirmed`, en cambio, exige confirmación humana y una columna
para cada ítem de la versión actual.

Un cambio de instrumento, reglas, columnas o hash de dataset debe invalidar el mapeo y
producir una nueva versión; no se actualizan puntuaciones ni resultados históricos en sitio.

## Reglas de validación

1. IDs únicos y referencias válidas en toda la jerarquía.
2. La relación variable-dimensión-indicador-ítem debe ser coherente.
3. Los códigos de respuesta son únicos por ítem; los códigos/rangos ambiguos se rechazan.
4. Un ítem invertido requiere extremos explícitos y la regla
   `min_plus_max_minus_value`; no se invierte por ser un dato numérico.
5. Suma y promedio solo aparecen cuando una regla confirmada los declara. No existe un método
   automático.
6. La política inicial no imputa ni prorratea: si falta un ítem requerido, la puntuación futura
   de esa dimensión será ausente, sin modificar el dataset original.
7. El alfa de Cronbach se calculará más adelante usando únicamente los ítems originales de una
   escala/dimensión confirmada y sus casos completos.

## Fixtures y cobertura

`fixtures/instruments/satisfaction_confirmed.context.json` representa un cuestionario sintético
de dos ítems y un mapeo confirmado. La prueba `backend/tests/test_instrument_context.py` valida el
caso correcto y rechaza: confirmación ausente, inversión sin rango y mapeo confirmado incompleto.

## Integración posterior

La Sesión 22B añadirá el adaptador del puerto y el motor de puntuaciones. Research seguirá creando
el dataset derivado solo después de una previsualización y confirmación explícita. Statistics
devolverá resultados deterministas y trazables, nunca escribirá en el dataset original ni decidirá
reglas metodológicas por sí solo.
