# Sesión 22B — diseño de confirmación y persistencia de puntuaciones

## Estado

Propuesta para revisión conjunta Research–Statistics. Este documento no modifica contratos
públicos ni autoriza todavía implementación, endpoints o migraciones.

## Objetivo

Confirmar una previsualización de puntuaciones y persistir un resultado derivado reproducible sin
aceptar puntuaciones enviadas por el cliente, sin modificar el dataset fuente y sin acoplar
Statistics a repositorios de Research.

## Flujo propuesto

1. El usuario solicita una previsualización con `project_id`, `instrument_id` y `scoring_rule_id`.
2. Orchestration obtiene contexto y filas mediante `InstrumentStatisticsBridge` y calcula
   `ScoringPreview`.
3. La interfaz presenta únicamente resultados derivados, conteos, confiabilidad, advertencias y la
   huella de la previsualización.
4. La confirmación recibe la identidad original, `preview_fingerprint`, una confirmación literal y
   una referencia opaca del confirmante; nunca recibe puntuaciones como fuente de verdad.
5. Orchestration vuelve a ejecutar autorización y cálculo. Si la nueva huella difiere, rechaza la
   confirmación como `stale`.
6. Research persiste de forma atómica el registro y, si se acuerda, el dataset derivado. Los
   reintentos de la misma confirmación devuelven el mismo resultado.

## DTO interno de confirmación

```text
ScoringConfirmationRequest
  project_id: UUID
  instrument_id: UUID
  scoring_rule_id: UUID
  preview_fingerprint: sha256
  confirm: Literal[True]
  confirmer_ref: string opaco
```

`confirmer_ref` debe provenir de la capa autenticada; no prueba autorización por sí mismo.

## Registro persistido propuesto

```text
InstrumentScoringRecord
  result_id: UUID
  project_id: UUID
  instrument_id: UUID
  instrument_version: int
  dataset_id: UUID
  dataset_hash: sha256
  scoring_rule_id: UUID
  preview_fingerprint: sha256
  scoring_engine_version: string
  status: Literal["persisted"]
  scores: resultados derivados o referencia al dataset derivado
  score_cases: total, valid, missing
  reliability: alpha opcional, valid_rows, excluded_rows, reason opcional
  warnings: lista
  confirmed_at: datetime UTC
  confirmer_ref: string opaco
  derived_dataset_id: UUID opcional
```

El registro es histórico e inmutable. Un cambio posterior de fuentes no sobrescribe resultados
anteriores; la vigencia actual se calcula contra instrumento, versión, dataset, hash, regla y
versión del motor.

## Estados

- `previewed`: respuesta efímera, no persistida.
- `confirmed`: transición lógica dentro de la operación de confirmación.
- `persisted`: único estado durable de esta entrega.
- `stale`: resultado de una revalidación fallida; no se persiste como éxito.
- `rejected`: solicitud inválida o no autorizada; no se persiste como éxito.

Para evitar estados intermedios huérfanos, `confirmed → persisted` debe ser una operación atómica.

## Idempotencia y concurrencia

- `preview_fingerprint` debe tener una restricción única en el alcance acordado.
- Repetir una confirmación ya aplicada devuelve el mismo `InstrumentScoringRecord`.
- Antes del cálculo, después de leer las filas y justo antes del commit se revalidan contexto,
  instrumento, mapeo, dataset, hash y regla.
- Si cambia cualquier fuente o la versión del motor, la huella deja de coincidir y la operación se
  rechaza sin escritura parcial.
- La escritura de metadatos y del dataset derivado debe seguir el patrón transaccional y de limpieza
  segura utilizado por Research para datasets preparados.

## Huella reproducible

Antes de habilitar persistencia, `ScoringPreview` debe incorporar `scoring_engine_version` a su
contenido firmado. La huella cubre identidades, versiones, hashes, regla, puntuaciones,
confiabilidad, conteos, advertencias y versión del motor; nunca filas originales ni rutas.

## Dataset derivado

Statistics entrega puntuaciones en el mismo orden de las filas autorizadas. Research decide y
documenta la materialización. La propuesta es crear un dataset nuevo e inmutable con
`source_dataset_id`, heredar la marca `synthetic` y añadir columnas de puntuación con nombres
deterministas. El dataset fuente nunca se modifica.

Debe ratificarse si el derivado conserva todas las columnas fuente o únicamente una clave interna
no sensible más las puntuaciones. No se implementará esta parte hasta cerrar esa decisión de
privacidad y trazabilidad.

## Responsabilidades

- **Statistics:** cálculo puro, versión del motor, resultado derivado y validaciones operativas.
- **Research:** autorización, repositorio, transacción, historial, dataset derivado y auditoría.
- **Orchestration:** recomputación, comparación de huella, idempotencia y coordinación atómica.

## Casos de prueba mínimos

1. Confirmación válida persiste exactamente una vez.
2. Reintento devuelve el mismo `result_id`.
3. Huella incorrecta o vencida se rechaza sin persistencia.
4. Cambio concurrente de instrumento, regla, dataset o hash se rechaza.
5. Cambio de `scoring_engine_version` invalida la huella previa.
6. Falla de almacenamiento no deja archivo ni registro parcial.
7. El dataset fuente permanece byte a byte intacto.
8. El registro histórico sigue legible aunque las fuentes actuales queden stale.
9. Una confiabilidad no calculable se persiste como metadato explícito, no como `0`.
10. No se exponen filas, rutas, bytes ni referencias internas mediante el DTO de confirmación.

## Decisiones que Research debe ratificar

1. Alcance exacto de la clave idempotente: huella global o huella más proyecto/instrumento/regla.
2. Contenido permitido del dataset derivado y estrategia de columnas no sensibles.
3. Ubicación y esquema del repositorio versionado.
4. Política de retención de previsualizaciones y resultados históricos.
5. Versión inicial y evolución de `scoring_engine_version`.
