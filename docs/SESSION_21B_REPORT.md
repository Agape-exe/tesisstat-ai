# Sesión 21B Contratos estadísticos de instrumentos

## Estado

Sesión cerrada. Research fusionó el contrato público `InstrumentContext v1.0.0`, su persistencia,
rutas, fixtures deterministas y adaptador autorizado a `develop`. Statistics revisó y aprobó el
PR #58, y su consumidor usa ya el contrato público.

## Resultado

El contrato es independiente de los seis contratos canónicos v1.0.0. Research conserva la
propiedad de extracción, revisión humana, persistencia, mapeos y futuros datasets derivados.
Statistics consumirá un contexto confirmado mediante un adaptador autorizado que se implementará
en una entrega posterior de 18A.

Las decisiones ratificadas son:

- `methodology_review_id` representa el `document_id` UUID asociado a la revisión, junto con
  `project_id`, versión y hash; no se crea un identificador metodológico ficticio.
- La vigencia de un dataset usa `dataset_id` y `dataset_hash`; `dataset_version` no forma parte
  del contrato.
- La única inversión v1 es `min_plus_max_minus_value`.
- El instrumento usa los estados `draft`, `reviewed` y `stale`; la confirmación humana es un
  estado independiente.
- El mapeo opcional usa los estados `draft`, `confirmed` y `stale` y requiere cobertura total,
  confirmación humana, identidad y hash del dataset cuando está confirmado.

## Artefactos

- `backend/app/shared/instrument_contracts.py`: DTO y validaciones canónicas.
- `backend/app/shared/ports.py`: puerto público `InstrumentContextReader`.
- `docs/contracts/instrument_context_v1.schema.json`: JSON Schema versionado.
- `docs/contracts/examples/`: fixtures reproducibles publicados por Research.
- `backend/tests/test_instrument_context.py`: consumo de contrato canónico y casos límite.

## Validación ejecutada

Las pruebas focalizadas de Statistics sobre contrato, conversión, puntuación, confiabilidad y
límites modulares finalizaron correctamente (`24 passed`), junto con Ruff.

## Compatibilidad y límites

No se modificaron `ResearchPackage`, `ResearchVariable`, `DatasetReference`, `AnalysisPlan` ni
`AnalysisResult` v1.0.0. La integración controlada aún no lee filas reales ni ejecuta E2E; el
motor de 22B sigue separado de repositorios y servicios internos de Research.

## Siguiente dependencia

La siguiente dependencia es una composición autorizada que entregue a Statistics un
`InstrumentContextReader` real y filas de un dataset confirmado. Esa coordinación habilitará la
primera prueba Research → Statistics de 22B.
