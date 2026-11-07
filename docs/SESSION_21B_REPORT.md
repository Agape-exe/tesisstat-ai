# Sesión 21B Contratos estadísticos de instrumentos

## Estado

Diseño técnico cerrado y ratificado con Research. La sesión define el intercambio
`InstrumentContext v1.0.0`; no implementa persistencia, rutas HTTP, adaptador de lectura,
puntuaciones ni confiabilidad.

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

- `backend/app/shared/instrument_context.py`: DTOs y validaciones del contrato.
- `docs/INSTRUMENT_CONTEXT_V1.md`: especificación de intercambio.
- `fixtures/instruments/`: caso confirmado y caso rechazado sintéticos.
- `backend/tests/test_instrument_context.py`: validación del contrato y de sus casos límite.

## Validación ejecutada

Se aprobaron 7 pruebas focalizadas: cinco de InstrumentContext y dos de límites modulares. Ruff,
formato, comprobación de contratos existentes y compilación también finalizaron correctamente.

## Compatibilidad y límites

No se modificaron `ResearchPackage`, `ResearchVariable`, `DatasetReference`, `AnalysisPlan` ni
`AnalysisResult` v1.0.0. Tampoco se integra todavía Statistics con Research: hasta que 18A entregue
el adaptador autorizado, los casos de 22B se mantienen como diseño y fixtures conceptuales.

## Siguiente dependencia

Research implementará 18A-1 en su rama independiente. Al compartir sus DTOs y JSON Schema finales,
Statistics comprobará compatibilidad antes de iniciar la implementación del motor de puntuaciones
en 22B.
