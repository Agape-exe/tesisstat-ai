# Diseño preparatorio de Sesión 22B Puntuaciones y confiabilidad

## Alcance diferido

Este documento prepara la implementación futura y no añade motor, rutas, persistencia ni
integración con Research. El único insumo contractual es `InstrumentContext v1.0.0` ratificado.

## Precondiciones para ejecutar una puntuación

1. El contexto tiene estado `reviewed` y confirmación humana vigente.
2. Existe `dataset_mapping` con estado `confirmed` para la misma versión del instrumento.
3. El `dataset_id` y `dataset_hash` coinciden con el dataset autorizado que Research entregará.
4. La regla de puntuación está confirmada, usa `sum` o `mean` y declara `all_required`.
5. Statistics recibe los datos mediante el futuro adaptador autorizado, no por una ruta de lectura
   libre ni por una ubicación proporcionada por el cliente.

## Diseño determinista propuesto

La futura operación recibirá un `InstrumentContext` confirmado y una `DatasetTable` ya autorizada.
No modificará la tabla original. Para cada regla:

1. Resuelve `item_id` a `column_name` exclusivamente desde `dataset_mapping`.
2. Valida cada respuesta contra la codificación explícita o el rango del ítem.
3. Distingue una respuesta ausente de un código desconocido o fuera de rango.
4. Aplica `min_plus_max_minus_value` solo a ítems con inversión confirmada.
5. Si falta cualquier ítem requerido, entrega puntuación ausente para esa dimensión u observación.
6. Aplica suma o promedio solo según la regla confirmada.
7. Devuelve valores derivados, casos válidos/excluidos, advertencias y trazabilidad de regla,
   instrumento, dataset y hash.

Los códigos inválidos, ambiguos o fuera de rango son errores de validación; no se convierten en
faltantes silenciosamente. La previsualización y persistencia del dataset derivado pertenecen a
Research y exigen confirmación humana adicional.

## Confiabilidad

El alfa de Cronbach reutilizará `statistics.inferential.cronbach_alpha` y recibirá solo los ítems
originales recodificados de una regla/dimensión confirmada. No se calculará sobre una puntuación
agregada. Usará casos completos y deberá informar cantidad de casos válidos y excluidos. Un alfa
alto no se presentará como evidencia única de validez.

## Matriz de casos de prueba

Los valores sintéticos y resultados esperados están en
`fixtures/instruments/scoring_design_cases.json`.

| Caso | Resultado esperado |
| --- | --- |
| Codificación directa e inversión | Recodificación explícita y suma/promedio exactos |
| Faltante requerido | Puntuación ausente sin cambiar la fila original |
| Código desconocido | Error de validación, no faltante |
| Fuera de rango | Error de validación, no faltante |
| Alfa con ítems recodificados | Alfa reproducible sobre ítems originales |
| Alfa con faltantes | Solo casos completos y conteo de excluidos |
| Escala constante | Error: varianza total cero |
| Muestra insuficiente | Error: menos de dos filas completas |

## Criterios para empezar 22B

No iniciar el motor hasta que Research publique los DTOs y JSON Schema definitivos de 18A-1 y el
equipo confirme que coinciden con el contrato ratificado. La persistencia, endpoints y el adaptador
autorizado pueden continuar en paralelo dentro de Research, pero no deben condicionar las pruebas
unitarias puras del motor.
