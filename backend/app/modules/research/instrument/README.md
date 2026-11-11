# C6 — Instrumento y puntuaciones v2

Local con guardas development/loopback; no autenticación remota ni despliegue.
Prefijo `P=/api/v2/research/projects/{project_id}/instruments`.
Las rutas v1 y extracción documental existentes permanecen compatibles.

- GET/POST `P`; GET/PATCH `P/{id}`; GET `P/{id}/revisions`.
  POST/PATCH: InstrumentEdit (`expected_revision,structure,context_field`). Servidor asigna
  IDs persistentes nuevos, conserva los existentes y traduce claves temporales.
- POST `P/{id}/confirm`: `expected_revision,confirm:true`. Confirma estructura y reglas,
  creando revisión. Solo exige el campo pertinente confirmado en Contexto, no contexto
  completo, documento ni hipótesis. Edición posterior crea borrador nuevo.
- GET/PUT `P/{id}/mapping`; GET `.../mapping/revisions`. PUT recibe revisiones esperadas,
  tabla real del proyecto, correspondencias por IDs y confirm. Borrador admite incompletos;
  confirmación exige cobertura total y relación 1:1; identificadores quedan fuera.
- POST `P/{id}/score-previews`: revisiones instrumento/mapeo, scoring_rule_id, column_name,
  confirm:true. Expira en 30 minutos; máximo 20 puntuaciones y 20 explicaciones. Calcula
  todas las filas, solo ítems de la regla y ninguna llamada a alfa.
- POST `P/{id}/scores`: preview_id/fingerprint/confirm:true/request_id UUID.
  GET `P/{id}/scores`: recibos históricos; no declara vigencia de sus fuentes al leerlos.

Instrumento, mapeo y reglas se resuelven en servidor. Opciones usan códigos exactos y
valores explícitos; números directos requieren reglas revisadas. Inversión antes de agregar,
una sola vez. Suma/promedio requieren todos los ítems de la regla. Ausentes, desconocidos y
fuera de rango se distinguen; nunca se imputan ni convierten en cero. Conteos de problemas
pueden solaparse por fila. Preview sin alfa, sin publicación de datos.

Confirmación revalida fingerprint/caducidad/versiones bajo la transacción SQLite de C3.
Publica score, todas las filas, linaje, contenido, recibos y diccionario juntos; rollback ante
fallo. Reintentos tras éxito devuelven el mismo histórico, incluso tras vencimiento. Una
clave de solicitud reutilizada con otro preview/fingerprint produce 409. No se activa dataset
global ni se confirma diccionario nuevo. Límites: 50 000 filas, 200 columnas, 10 MiB.

Extensión explícita ScorePublicationPort/ScoreDerivedTableV2. Inventario, TableReadPort,
perfiles, diccionarios y preparación posterior aceptan este derivado real; no tiene receta
prepare/join ficticia. Cambios de instrumento/mapeo/regla/recodificación o fuentes lo dejan
obsoleto, conservando contenido y recibos. Se impiden ciclos de dependencias del instrumento.

Confiabilidad usa Análisis: instrumento/regla elegidos explícitamente, constructo y
pertinencia revisados, diagnóstico, propuesta, autorización local de fuentes si procede,
aprobación y ejecución. DiagnosticService.reliability_inputs ofrece la vista autorizada de
ítems recodificados desde la tabla original versionada; nunca usa el total. Congela refs y
revalida con C5. Cronbach no calculable se registra not_executed sin métricas ni conclusión;
negativo se conserva con advertencia. Alfa no demuestra validez ni unidimensionalidad.

Las invariantes v1 de ítems/jerarquía se reutilizan sin procedencia documental inventada.
No se amplió extracción documental v2 ni se adoptan resultados v1 sin revisión humana.
Persistencia remota debe implementar scope/RLS y protocolo equivalente; la transacción
SQLite no promete atomicidad de filesystem externo/Storage ni restauración de backup.
