# Contexto manual v2 (S02)

S02B añade **Completar con ayuda de otro chat**: prompt español versionado, interpretación
determinista sin credenciales de IA, propuesta persistida aislada y revisión editable.
API y semántica precisas: [contrato S02B](../../../../../docs/CONTRATOS_EVOLUCION.md#s02b--contrato-ejecutable-de-importación-asistida).
GET `/import-prompt`, POST/GET `/suggestions`, GET `/suggestions/{id}`,
POST `/suggestions/{id}/apply|reject`. Guardar no confirma por defecto. Listas se añaden con
selección por elemento y UUID servidor; CAS y recibo son atómicos e idempotentes.
Los campos que el usuario corrige tras importar conservan su origen IA y el historial.
Ejemplos sintéticos: `fixtures/context-import/` en la raíz del repositorio.

Corrección de revisión S02B: la entidad general estudiada es opcional y no describe las
filas de tablas (`row_meaning`, en Datos). observations se consulta como antecedente legado;
no se ofrece como requisito/confirmación global. GET refresca preguntas derivadas sin
reescribir hechos, confirmaciones ni históricos. Prompt `context-prompt-1.1` requiere unknown
y relaciones narrativas. Propuestas antiguas se previsualizan normalizadas a nota/unknown,
sin modificar el original persistido; backend rechaza seleccionar observations para aplicar.
Hipótesis H0/H1 y direcciones anteriores se conservan; dirección es detalle opcional, no
aprobación unilateral. La comparación y sus relaciones se resolverán por intención en S04.

Operaciones disponibles en la composición local `research.dev_app`, bajo
`/api/v2/research/projects/{project_id}/context`:

- GET: contexto actual o vacío virtual (`revision=0`, `updated_at=null`), sin insertar.
- PATCH: `{expected_revision, changes, confirm_fields}`. Omitir conserva; null borra;
  listas null se convierten en `[]`. Solo admite valores crudos, nunca Facts del cliente.
- GET `/revisions`: revisiones completas, de más reciente a más antigua.

Los proyectos se comprueban antes de leer/escribir. IDs de proyecto se normalizan como UUID.
El repositorio es un puerto; SQLite usa una conexión por operación, `BEGIN IMMEDIATE`,
compara revisión y añade una fila histórica en la misma transacción. No actualiza ni borra
revisiones. Una creación concurrente también usa CAS desde revisión cero. No modifica tablas
legadas ni migra bases existentes. Los errores v2 tienen el sobre acordado y un fallo de
almacenamiento devuelve 503, no contexto vacío. La protección loopback/development continúa.

Cada objetivo/hipótesis nuevo omite `id`; el servidor devuelve UUID. En ediciones debe enviarse
su ID existente: IDs arbitrarios, duplicados o de otro proyecto se rechazan. Las listas se
envían completas; se preservan los Facts de elementos iguales por ID incluso al reordenar.
Una hipótesis puede referenciar un objetivo ya guardado de este contexto. Para retirarlo,
retira o desvincula sus hipótesis en el mismo PATCH. La UI realiza esta desvinculación visible
en el selector. Cambiar texto, vínculo o dirección de hipótesis invalida su confirmación.

Confirmaciones: JSON Pointer al documento resultante, por ejemplo `/main_objective`,
`/specific_objectives/0/text`, `/hypotheses/0/statement`, `/complementary_notes/0`.
Se usan índices JSON normales, no IDs como índices; IDs son referencias durables entre
recursos. CAS impide confirmar índices de una lista de otra revisión inadvertidamente.
En hipótesis existentes, omitir objective_id o alternative conserva sus metadatos;
objective_id=null desvincula de manera explícita.
Confirmar sin modificar crea otra revisión. Cada confirmación lleva revisión, fecha UTC y
actor del servidor. En esta composición local el actor es `local`; no es un usuario
autenticado. Los hechos no modificados mantienen procedencia y confirmación originales.
Enviar de nuevo el mismo valor no es editarlo. Unknown/null/vacío no se confirman.

No hay intención seleccionada en GET de C2: el estado es empty o partial según contenido.
`usable` queda reservado a evaluación por intención en S04. Las preguntas pendientes orientan
una propuesta futura; ninguna bloquea la carga/perfil. No se evalúa elegibilidad científica
global, ni se crea intención/snapshot implícitamente al guardar.

La UI guarda antes de confirmar, permite selección múltiple, muestra historial y conserva el
borrador ante errores. Un 409 requiere consultar la revisión actual y elegir explícitamente
reaplicar los campos locales o usar el servidor; ofrece descargar el borrador. Reaplicar una
lista sustituye toda esa lista y puede requerir ajustar vínculos si otra edición retiró IDs.
Las confirmaciones se revisan de nuevo. No hay combinación automática que oculte conflictos.

Documentos/metodología v1 siguen como herramientas opcionales: esta entrega no copia contenido
documental ni equipara sus revisiones a confirmaciones C2. El chat sigue con sus consumidores
legados; no usa automáticamente este contexto. No hay consumo IA al guardar/confirmar.

Los modelos C4 en `shared/analysis_v2.py` son estructura preparada, sin operaciones de
intenciones/snapshots/propuesta/ejecución nuevas. S04 deberá resolver y autorizar cada SourceRef
en servidor, comprobar pertenencia/revisión/hash, diccionario/columnas y ausencia de ciclos.
El validador estructural no demuestra existencia de fuentes externas ni autoriza su uso.
