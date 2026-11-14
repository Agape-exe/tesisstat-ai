# Respuestas sintéticas S02B

`ventas.json` comprueba un estudio descriptivo sin hipótesis; `educacion.json` incluye
una hipótesis y su referencia local; `encuesta-organizacional.json` es parcial e incorpora
una propiedad adicional para proponerla como nota. No son tesis ni resultados científicos.
Se pueden pegar directamente o dentro de un único bloque Markdown JSON. El importador
normaliza propiedades adicionales a notas antes de validar el DTO canónico estricto.
Las pruebas validan los ejemplos normalizados contra el JSON Schema canónico.

`grupos-y-sesiones.json` sigue el prompt 1.1: grupos A/B, notas antes/después vinculables y
cuestionarios anónimos no vinculables por sesión, relaciones conservadas narrativamente y
observations=unknown; H0/H1 sin dirección inferida de «favorable». `educacion.json` conserva
deliberadamente paired como respuesta anterior para probar adaptación a nota revisable.
Ningún ejemplo permite aplicar paired a todo el proyecto ni asignar contextos a tablas.
Los CSV `notas-grupos.csv` y `cuestionarios-anonimos.csv` son fuentes sintéticas para revisar
row_meaning por tabla, sin cálculo estadístico ni datos personales reales.
