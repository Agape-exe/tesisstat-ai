# Revisión de compatibilidad 21B con Research 18A

## Propósito

Este artefacto es la línea base para comparar la futura entrega verificable de Research 18A-1 y
18A-2. No inspecciona la rama local de Research, no modifica sus archivos y no constituye una
prueba E2E.

## Matriz de comparación requerida

| Área | Statistics espera | Verificación al recibir 18A |
| --- | --- | --- |
| Identidad | `instrument_id`, `project_id`, versión y estados `draft/reviewed/stale` | Tipos UUID, enteros y enums iguales |
| Revisión metodológica | `methodology_review_id` es el `document_id` de la revisión | Confirmar que no se introdujo UUID ficticio |
| Procedencia | Hashes SHA-256 y documento opcional | Confirmar hashes y nulos coherentes |
| Confirmación | `pending/confirmed`, fecha para confirmado | Validar contexto y mapeo |
| Jerarquía | variable → dimensión → indicador → ítem | Confirmar IDs estables y referencias válidas |
| Ítems | tipo, opciones, rango, inversión | Única regla: `min_plus_max_minus_value` |
| Reglas | `sum/mean`, `all_required`, confirmación | No imputación ni prorrateo v1 |
| Mapeo | `dataset_id`, `dataset_hash`, `instrument_version` | Confirmar cobertura completa y ausencia de `dataset_version` |
| Seguridad | Sin filas, rutas ni secretos | Revisar DTO y JSON Schema |
| Lectura | `get_confirmed_context(project_id, instrument_id)` | Revisar firma y rechazo de contextos no confirmados |

## Pruebas de consumo preparadas

`backend/tests/test_scoring_context.py` consume solo el DTO compartido y fixtures sintéticos. Cubre
conversión de contexto confirmado a especificaciones puras, puntuación con inversión, alfa sobre
ítems recodificados y rechazo de un contexto sin mapeo confirmado.

No importa implementaciones internas de Research, no invoca `ResearchInstrumentContextReader` y no
accede a SQLite. Cuando la rama 18A sea pública, se añadirá una prueba de compatibilidad que valide
un fixture exportado por Research contra este consumidor y el JSON Schema ratificado.
