# C4 S04A: intenciones y diagnósticos

Prefijo `P=/api/v2/research/projects/{project_id}`. Solo demo local; no despliegue.
Sin documento, hipótesis, dataset activo v1 ni proveedor IA. Cada análisis tiene UUID propio.

- GET/POST `P/intents`; GET/PATCH `P/intents/{id}`; GET `.../{id}/revisions`.
  Entrada `IntentPatch`: `expected_revision`, `changes`, `confirm=false` por defecto.
  PATCH conserva campos omitidos; listas null → vacías. Texto null → desconocido.
  Cambiar o guardar retira la revisión/confirmación anterior; `confirm=true` confirma
  únicamente respuestas conocidas de esta intención, con actor/fecha/revisión servidor.
  Unknown permite borrador, pero no una intención global confirmada sin tipo/estimando.
  Los valores unitarios no demuestran independencia ni aprueban técnicas.
- POST `P/diagnostics`: `intent_id,intent_revision,dataset_id,dataset_revision,checks,confirm:true`.
  GET `P/diagnostics?intent_id=...`; GET `P/diagnostics/{id}`. GET nunca calcula ni escribe.
  `checks` allowlist: complete_cases, group_sizes, paired_cases, distribution, normality,
  homogeneity, influence. No final contrast, recomendador, plan, aprobación ni ejecución v2.

Canónicos: `shared/analysis_v2.py`, `shared/diagnostics_v2.py`, `intents/models.py`.
Exportadores generan schemas y TypeScript. S04A añade `dataset_id` opcional y Facts
`observational_unit`, `identification`, `comparison_notes`, `linkage`, además de
`identifier_column_id`. No se copian Facts de C2. `paired_columns` exige dos columnas distintas.
Una intención trabaja sobre una tabla analítica real; esta puede ser un derivado con varios
padres. Para archivos separados, usar la preparación confirmada S03B: no unir aquí por posición.

`IntentService` valida pertenencia y vínculos con diccionario/tabla. `DiagnosticService`
coordina `WorkspaceService.read_table` (puerto TableReadPort, todas las filas y antecesores),
diccionario guardado y perfil vigente. Verifica hashes JSON y reconstruye referencias en servidor.
La UI permite actualizar el perfil explícitamente si falta o está obsoleto. Un diccionario
virtual necesita al menos un guardado; no es obligatorio confirmar todas sus variables.

`statistics.diagnostics.evaluate` recibe solo modelos/filas autorizados. Usa casos completos
conjuntos de TODAS las variables seleccionadas, marcadores del diccionario y exclusiones
numéricas adicionales solo para escalas cuantitativas confirmadas, nunca por apariencia.
El `profile` de DiagnosticV2 contiene filas totales, casos efectivos, faltantes/invalidos,
grupos, pares y diferencias cero. Un identificador opcional valida unicidad/presencia,
pero no demuestra pertinencia científica de la comparación. Sin vínculo revisado no se
calculan diferencias. El sentido es primera−segunda, igual que las funciones puras legadas.

Persistencia append-only en `analysis_evidence_v2`, clave proyecto/tipo/recurso/revisión.
`EvidenceStore` es el puerto; `SQLiteEvidenceStore` el adaptador. CAS con BEGIN IMMEDIATE.
El cálculo ocurre fuera del lock; antes de INSERT se releen y comparan TODAS las dependencias
bajo el mismo lock de escritura SQLite que C2/C3/intención. Cambios durante cálculo → 409,
sin publicar. Fallos de persistencia → rollback/503. Los originales S03A conservan su protocolo
filesystem; no se afirma atomicidad entre filesystem/SQLite ni ante modificaciones externas.

`state=current|stale` y `stale_reason` son proyección al leer: no reescriben checks ni payload
histórico. Otra revisión de intención/diccionario/perfil, contexto de tabla o fuente/antecesor
deja obsoleta la evidencia dependiente, conservando vigente la de dependencias intactas.
Una nueva ejecución de
diagnóstico siempre genera otro ID; no hay promesa de idempotencia por request_id.

S04B consumirá `IntentService`, `DiagnosticService.resolve/get/list`, `EvidenceStore`,
`DiagnosticV2.profile/checks/source_refs` y `statistics.numerical_policy`. Debe verificar vigencia
de nuevo al proponer/aprobar/ejecutar y construir AnalysisSnapshotV2 en servidor. Debe reutilizar
las mismas políticas de selección de casos; no fabricar paquetes/hipótesis v1, inferir técnica
por n=50 o p de normalidad, ni reutilizar confirmaciones como aprobación final.

## C5 incorporado en S04B

`orchestration.analysis_v2_service.AnalysisServiceV2` consume este servicio, el puerto
TableReadPort y `EvidenceStore`. C5 registra snapshot/propuesta, autorización local de
fuentes, aprobación explícita, reserva transaccional, intentos y resultados. Los tipos
canónicos adicionales viven en `shared/plans_v2.py`; rutas bajo `P/analysis`.

`IntentPatch` añade `objective_id`, `hypothesis_id`, `requested_technique` y cambios
parciales de `conditions`; roles ya disponibles se editan también en la interfaz.
Se verifican vínculos reales al Contexto del mismo proyecto. Condiciones nuevas:
`inference_reviewed`, `influence_reviewed`, `sampling_limit_accepted`, `review_notes`.
Confirmación siempre servidor. Guardar una nueva revisión retira las confirmaciones
anteriores y deja obsoletas sus evidencias dependientes; no altera payloads aprobados.

`statistics.planning_v2` es la política reutilizable por el futuro tutor.
`statistics.diagnostics.select_cases` comparte casos efectivos con `execution_v2`.
Wilcoxon conserva pares completos y además informa n sin ceros: used/excluded C5 reflejan
el contraste, mientras el perfil diagnóstico mantiene complete_pair_count y zero_difference_count.
Detalle, límites, recuperación de reservas y evidencia: [S04B](../../../../../docs/sesiones/S04B.md).
