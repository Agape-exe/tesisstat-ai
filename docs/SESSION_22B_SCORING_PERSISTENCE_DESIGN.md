# Sesión 22B — diseño de confirmación y persistencia de puntuaciones

## Estado

Propuesta actualizada con las decisiones ratificadas por Research y Statistics, pendiente de
aprobación documental final. Este documento no modifica contratos públicos ni autoriza todavía
implementación, endpoints o migraciones.

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
4. La confirmación recibe la identidad original, `preview_fingerprint` y una confirmación literal;
   nunca recibe puntuaciones como fuente de verdad. La capa autenticada y autorizada incorpora
   internamente la referencia opaca del confirmante.
5. Orchestration vuelve a ejecutar autorización y cálculo. Si la nueva huella difiere, rechaza la
   confirmación como `stale`.
6. Research persiste el registro histórico y sus puntuaciones en una única transacción SQLite. Los
   reintentos de la misma confirmación devuelven el mismo resultado.

## DTO interno de confirmación

```text
ScoringConfirmationRequest
  project_id: UUID
  instrument_id: UUID
  scoring_rule_id: UUID
  preview_fingerprint: sha256
  confirm: Literal[True]
```

La capa de aplicación construye después un comando interno que añade `confirmer_ref`. Esta
referencia debe provenir de la identidad autenticada y autorizada del servidor: no puede ser un
valor libre del cliente y no prueba autorización por sí misma.

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
  scoring_engine_version: Literal["1.0.0"]
  status: Literal["persisted"]
  scores: puntuaciones almacenadas en una tabla relacionada
  score_cases: total, valid, missing
  reliability: alpha opcional, valid_rows, excluded_rows, reason opcional
  warnings: lista
  confirmed_at: datetime UTC
  confirmer_ref: string opaco
```

El registro es histórico e inmutable y utiliza un `result_id` propio. Un cambio posterior de
fuentes no sobrescribe resultados anteriores; la vigencia actual se calcula contra instrumento,
versión, dataset, hash, regla y versión del motor.

## Estados

- `previewed`: respuesta efímera, no persistida.
- `confirmed`: transición lógica dentro de la operación de confirmación.
- `persisted`: único estado durable de esta entrega.
- `stale`: resultado de una revalidación fallida; no se persiste como éxito.
- `rejected`: solicitud inválida o no autorizada; no se persiste como éxito.

Para evitar estados intermedios huérfanos, `confirmed → persisted` debe ser una operación atómica.

## Idempotencia y concurrencia

- La clave idempotente es
  `(project_id, instrument_id, scoring_rule_id, preview_fingerprint)` y tiene una restricción
  única.
- Repetir una confirmación ya aplicada devuelve el mismo `InstrumentScoringRecord`.
- El reintento no modifica `confirmed_at`, `confirmer_ref` ni ningún otro dato de la confirmación
  original.
- Antes del cálculo, después de leer las filas y justo antes del commit se revalidan contexto,
  instrumento, mapeo, dataset, hash y regla.
- Si cambia cualquier fuente o la versión del motor, la huella deja de coincidir y la operación se
  rechaza sin escritura parcial.
- En esta primera entrega, el registro y sus puntuaciones se escriben en una única transacción
  SQLite. No se asume atomicidad entre SQLite y archivos externos.

## Huella reproducible

Antes de habilitar persistencia, `ScoringPreview` debe incorporar
`scoring_engine_version = "1.0.0"` a su contenido firmado. Esta versión evoluciona de forma
independiente a la versión de la aplicación. La huella cubre identidades, versiones, hashes, regla,
puntuaciones, confiabilidad, conteos, advertencias y versión del motor; nunca filas originales ni
rutas.

## Dataset derivado

La materialización de un dataset derivado queda pospuesta hasta estabilizar el repositorio
histórico. La primera entrega persiste únicamente el registro y sus puntuaciones dentro de SQLite.

Cuando se implemente la materialización, se aplicará minimización de datos: el nuevo dataset será
inmutable e incluirá únicamente un índice ordinal interno, las puntuaciones derivadas y los
metadatos técnicos indispensables. No copiará columnas originales, identificadores personales ni
rutas de almacenamiento. El dataset fuente nunca se modifica.

La referencia a ese dataset se incorporará mediante una migración futura; no forma parte del
esquema inicial de persistencia.

Una futura operación que coordine SQLite y archivos necesitará un protocolo explícito de
compensación o publicación; no se asumirá atomicidad entre ambos medios.

## Responsabilidades

- **Statistics:** cálculo puro, versión del motor, resultado derivado y validaciones operativas.
- **Research:** autorización, repositorio SQLite, transacción, historial y auditoría.
- **Orchestration:** recomputación, comparación de huella, idempotencia y coordinación atómica.

## Repositorio y retención

- Research implementará un repositorio SQLite interno, sin dependencias desde el motor estadístico.
- El esquema tendrá tablas separadas para registros históricos y sus puntuaciones, relacionadas por
  el `result_id` inmutable.
- Las previsualizaciones permanecerán exclusivamente en memoria.
- Los resultados persistidos se conservarán según el ciclo de vida del proyecto y una política de
  retención institucional configurable.
- No se implementarán vencimientos ni eliminaciones automáticas hasta que exista una política
  institucional definida.

## Casos de prueba mínimos

1. Confirmación válida persiste exactamente una vez.
2. Reintento devuelve el mismo `result_id`.
3. Huella incorrecta o vencida se rechaza sin persistencia.
4. Cambio concurrente de instrumento, regla, dataset o hash se rechaza.
5. Cambio de `scoring_engine_version` invalida la huella previa.
6. Falla dentro de la transacción SQLite no deja registros ni puntuaciones parciales.
7. El dataset fuente permanece byte a byte intacto.
8. El registro histórico sigue legible aunque las fuentes actuales queden stale.
9. Una confiabilidad no calculable se persiste como metadato explícito, no como `0`.
10. No se exponen filas, rutas, bytes ni referencias internas mediante el DTO de confirmación.
11. El cliente no puede elegir ni suplantar `confirmer_ref`.
12. Un reintento conserva la referencia y la fecha de la confirmación original.

## Decisiones ratificadas

1. La clave idempotente será
   `(project_id, instrument_id, scoring_rule_id, preview_fingerprint)`.
2. La materialización del dataset derivado se pospone; cuando exista, contendrá únicamente índice
   ordinal, puntuaciones y metadatos técnicos no sensibles.
3. Research será propietario de un repositorio SQLite interno con registros y puntuaciones en
   tablas separadas.
4. Las previsualizaciones serán efímeras; los históricos seguirán el ciclo del proyecto y una
   política institucional configurable, sin eliminación automática inicial.
5. La versión inicial del motor será `1.0.0`, independiente de la aplicación y cubierta por el
   fingerprint.
