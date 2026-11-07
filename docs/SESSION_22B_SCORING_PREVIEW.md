# Sesión 22B — previsualización de puntuaciones

## Alcance

`InstrumentScoringPreviewService` coordina el bridge autorizado de Research con el motor puro de
Statistics y devuelve una previsualización determinista en memoria. Esta entrega no persiste
resultados, no crea datasets derivados, no expone endpoints y no representa confirmación humana.

## Interfaz interna

La solicitud `ScoringPreviewRequest` contiene exclusivamente:

- `project_id`
- `instrument_id`
- `scoring_rule_id`

El servicio invoca `InstrumentStatisticsBridge.get_authorized_instrument_data(...)`. La respuesta
`ScoringPreview` contiene:

- estado único `previewed`;
- identidad y versión del instrumento;
- identidad y hash del dataset confirmado;
- regla utilizada;
- versión independiente del motor de puntuaciones (`1.0.0`);
- puntuaciones derivadas, sin filas originales;
- conteos totales, válidos y faltantes;
- alfa de Cronbach y conteos de casos completos cuando es calculable;
- advertencias operativas;
- huella SHA-256 determinista de todo el contenido derivado.

## Reglas operativas

- Una falla de autorización, vigencia, codificación o rango impide crear la previsualización.
- Los faltantes permitidos por `all_required` producen puntuaciones `null` y conteos explícitos.
- Si alfa no es calculable, la puntuación puede previsualizarse y la confiabilidad queda marcada
  como `not_calculable` con su motivo.
- La huella cambia si cambia cualquier identidad, resultado, conteo, advertencia, confiabilidad o
  versión del motor de puntuaciones.
- La respuesta no incluye columnas, respuestas originales, rutas, bytes ni referencias internas
  de persistencia.

## Verificación

Las pruebas deterministas cubren puntuaciones `2, 4, 6, 8, 10`, alfa `1.0`, faltantes,
confiabilidad no calculable, rechazo de códigos desconocidos, estabilidad de la huella y ausencia
de filas originales en la serialización. También verifican que la versión inicial sea `1.0.0` y
que un cambio de versión invalide la huella anterior.
