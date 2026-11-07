# Sesión 22B — plan de integración controlada

## Alcance

Este plan verifica el recorrido autorizado Research → Statistics para puntuaciones y
confiabilidad. No crea endpoints públicos de filas, no permite rutas de archivos controladas por
clientes y no altera `InstrumentContext v1.0.0` ni las fórmulas del motor.

La composición residirá en `app/orchestration/`. Research resuelve el contexto y dataset; Statistics
recibe exclusivamente el contexto canónico y filas previamente autorizadas.

## Precondiciones de entrega

Antes de invocar Statistics, la composición debe comprobar:

1. El `project_id` pertenece tanto al instrumento como al dataset.
2. El lector autorizado devuelve un contexto `reviewed` con confirmación `confirmed`.
3. El `dataset_mapping` existe, está `confirmed`, tiene confirmación humana y cubre todos los ítems.
4. `dataset_mapping.instrument_version == context.version`.
5. El dataset resuelto conserva `dataset_id` y `dataset_hash` coincidentes con el mapeo.
6. El contexto y el dataset siguen vigentes después de leer las filas.

Si falla cualquier comprobación, no se invoca el motor y no se devuelve un resultado parcial.

## Matriz de pruebas deterministas

| Caso | Preparación | Resultado esperado |
| --- | --- | --- |
| Éxito | Builder confirmado, mapeo completo, regla `sum` | Las filas autorizadas producen la puntuación y trazabilidad esperadas. |
| Inversión | Ítem con `min_plus_max_minus_value` | Solo el ítem marcado se recodifica; suma/promedio coincide exactamente. |
| Confiabilidad | Cuatro filas completas recodificadas | Alfa se calcula sobre ítems originales recodificados y reporta casos válidos. |
| Faltante requerido | Una celda mapeada ausente | La observación queda sin puntuación, sin mutar la fila fuente. |
| Código inválido | Código fuera de `response_options` | Error explícito de validación, nunca faltante silencioso. |
| Contexto stale | Cambio metodológico posterior a confirmación | El lector o la segunda comprobación rechaza el flujo. |
| Dataset stale | Cambio de bytes/hash durante la lectura | Se descarta todo el resultado. |
| Mapeo incompleto | Falta una columna o ítem | Research rechaza antes de entregar filas. |
| Versión divergente | `instrument_version` distinta de contexto | Research rechaza antes de entregar filas. |
| Rango semiacotado | Ítem numérico con un solo límite | El DTO público valida; Statistics rechaza únicamente la operación de puntuación con mensaje operativo. |

## Límites de responsabilidad

- **Research:** `ResearchInstrumentContextReader`, `DatasetService`, `iter_dataset()`, hash,
  autorización y filtrado exclusivo a columnas del mapeo.
- **Statistics:** `scoring_inputs_from_context`, puntuaciones, alfa de Cronbach, tratamiento de
  faltantes y errores de codificación.
- **Ambos:** fixture/harness determinista, aserciones de trazabilidad y regresiones de frontera.

## Criterio de cierre

La integración queda aceptada cuando el harness determinista supera toda la matriz, demuestra que
Statistics no importa repositorios internos de Research y mantiene el dataset original sin cambios.
