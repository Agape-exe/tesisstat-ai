# C3 S03B: tablas, variables y preparación opcional

Local, sin IA externa. Todas las rutas usan
`P=/api/v2/research/projects/{project_id}` y verifican pertenencia al proyecto.
`research.dev_app` conserva guardas loopback/development. No implementa autenticación remota.
Canónicos: `shared/data_workspace_v2.py`. Entradas estrictas: `data_workspace/models.py`.

## Adaptación de fuentes y lectura para S04

`DatasetRefV2` identifica una tabla **real**: `kind=imported|derived`, `format=table_json`,
revisión 1 inmutable, columnas UUID, nombre, conteos, `hash_algorithm=table-json-v1`,
`source_refs`, `synthetic:bool|null` y referencia opcional a la receta. No representa un
CSV/XLSX descargable. Original y extracción S03A se conservan con sus contratos propios.

`WorkspaceService.read_table(project_id,table_id,expected_revision?,expected_hash?)`
implementa `TableReadPort`: devuelve `(DatasetRefV2,todas_las_filas)`; valida proyecto,
bytes/hash, revisión/hash esperados, inclusión y vigencia de todos los antecesores.
No usa el preview, no activa el dataset v1 y no convierte texto/códigos/fórmulas.
Los derivados pueden ser fuentes de otras preparaciones/combinaciones.

`table-json-v1` sigue siendo SHA-256 del JSON UTF-8 compacto con claves, en este orden,
`columns` y `rows`, Unicode sin escape y celdas `string|null`. Es compatible con S03A.
`SourceRef(kind=dataset)` apunta al hash de contenido de esa tabla; para estos recursos no
es `research-dataset-v1`. Referencias de metadatos/diccionario/perfil usan `json-sort-v1`;
la nueva referencia `preparation` usa el hash canónico de la receta inmutable, sin ciclos.
Los seis contratos v1 y `compute_dataset_hash` permanecen intactos.

## Recursos HTTP

- GET `P/data-tables`: referencias importadas incluidas y derivados, sin filas.
- GET `P/data-summary`: evidencia real por tabla: perfil vigente/obsoleto/ausente,
  variables confirmadas/total, derivados y fuentes utilizables. No acredita revisión global.
- GET `P/data-tables/{id}/preview`: referencia y primeras 20 filas; exige fuente utilizable.
- GET/PATCH `P/data-tables/{id}/dictionary`, GET `.../dictionary/revisions`.
- GET `P/data-tables/{id}/profile`, GET `.../profile/revisions`: solo evidencia persistida;
  404 significa ausente; GET actual puede marcar `state=stale`, sin recalcular ni reescribir.
- POST `.../profile`: `{dataset_revision,dataset_hash,confirm:true}` calcula explícitamente.
- POST `P/table-preparations/preview`: recibe `TableRecipeV2`, guarda una vista previa de
  30 minutos. POST `P/table-preparations/apply`: `{preview_id,recipe_hash,confirm:true}`.
- GET `P/derived-tables/{id}`: recibo histórico, receta, fuentes y linaje completo.

Se usa `/data-tables` para compartir operaciones entre importadas y derivadas sin cambiar
las rutas `/tables` de S03A ni `/datasets` v1. PATCH sustituye el PUT completo propuesto en
S00: conserva campos omitidos y facilita recuperación de borradores concurrentes.

## Diccionario y evidencia

GET inicial sugiere una variable por columna con UUID determinista servidor, nombre del
encabezado y escala desconocida, sin confirmaciones. El recurso virtual tiene revisión 0;
guardar crea revisiones inmutables. El mismo ID de tabla no comparte variables con otra.
PATCH exige `{expected_revision,dataset_revision,dataset_hash,changes,confirm_fields}`;
`changes` se indexa por IDs reales de variables. Cada cambio admite nombre, descripción,
escala, columna (lista de 0–1 IDs), orden de categorías, marcadores e identificador.
Ejemplo de confirmación: `/variables/{variable_id}/identifier_confirmed`.

Omitir conserva; null borra o deja listas vacías; se retiran confirmaciones afectadas.
`false` confirmado es conocido. No se admiten actores/fechas/procedencia/confirmaciones del
cliente. Confirmar asigna actor local y fecha/revisión del servidor, incluso sin editar.
Escala ordinal confirmada requiere orden explícito que cubra categorías observadas no
faltantes; se pueden incluir categorías previstas aún no observadas. No se infiere orden
por códigos. Escala desconocida no se confirma. Descripción y diccionario completo no son
obligatorios. Roles independiente/dependiente no pertenecen a este recurso.

`field_confirmations` audita vínculo, orden y política de faltantes; los demás usan Fact.
Hash canónico excluye ambas formas de confirmación; referencias incluyen también revisión.
CAS usa `BEGIN IMMEDIATE`. 409 conserva el borrador de sesión por proyecto/tabla y ofrece
comparar valores y reaplicar solo cambios editados sobre la revisión nueva. Históricos
guardados siguen consultables aunque se excluya una fuente; no habilitan cálculos con ella.

El perfil adapta `ExploratoryAnalyzer.analyze_rows`, no otro importador. Usa todas las filas,
políticas por columna y detección de duplicados exactos sin eliminarlos. Presenta presentes,
faltantes, constantes/vacías, sugerencias de almacenamiento/identificador y top 10 frecuencias
con denominador de presentes. Almacenamiento sugerido no es escala humana. `storage_type`
del diccionario es una sugerencia inicial desconocida; evidencia actual vive en el perfil.
Solo una escala intervalar/razón confirmada, sin identificador aceptado y con todos los
presentes numéricos permite mínimo/máximo/media/mediana y DE muestral (n>1). No se promedian
nominales/ordinales/desconocidos. Cifras fuera de exponente ±308 o 1000 dígitos se declaran
no calculables en el resumen, conservando valores y frecuencias. Fórmulas son texto sin
evaluación. No hay normalidad, p-valores, nuevas recomendaciones ni envío de filas al chat.

Vacíos y null siempre faltan; marcadores adicionales se comparan con trim/casefold.
Duplicados comparan filas completas exactas. Perfil guarda método/versiones, referencias,
hashes, política y revisión del diccionario. Cualquier revisión de diccionario o referencia
de origen vuelve obsoleto el perfil: invalidación conservadora, incluso ante cambios de
descripción. GET no lo actualiza automáticamente.

## Recetas y publicación

Join: dos tablas distintas del proyecto, clave por tabla, columnas seleccionadas y nombres
de salida únicos, política obligatoria `matches_only|all_cases`. `exact-text-v1` compara
texto sin normalizar mayúsculas, espacios o ceros; 001 ≠ 1. Faltantes no se unen entre sí.
Claves repetidas no faltantes bloquean la confirmación; preview muestra conteos y motivo,
sin inventar una salida eligiendo una de ellas. No hay many-to-many, fuzzy ni unión por fila.
La salida mantiene coincidencias en orden izquierdo y luego exclusivos izquierdo/derecho;
los huecos son null, nunca cero. Vista previa incluye hasta 20 casos sin pareja por fuente
y los índices completos de sus filas de datos (base 1, sin encabezado).

Preparación reutiliza `transform_rows` del motor v1 para renombrar/eliminar columnas y
la política común de faltantes; eliminación explícita de filas con faltantes/duplicados y
reemplazo constante conservan correspondencia de filas. No hay catálogo nuevo ilimitado.
La receta usa IDs de columnas, también tras renombrar; una columna eliminada no se reutiliza.
Se preservan null, texto, espacios y fórmulas inertes porque el resultado es JSON, no CSV.

Confirmar revalida fuentes, diccionarios, receta, versión, vencimiento y hash de resultado
bajo bloqueo de escritura SQLite. Genera IDs propios, todas las fuentes, conteos, linaje
de cada columna (incluida eliminación con vínculo null) y correspondencia de todas las
filas. Copia definiciones con procedencia derived y confirmaciones retiradas; vínculos
eliminados quedan pendientes.
En combinaciones, el diccionario proyecta solo columnas elegidas; las definiciones omitidas
siguen disponibles en los diccionarios de origen y su linaje queda registrado.
No confirma población/diseño ni hereda consentimiento IA, propiedad o aprobación de análisis.
Sintético solo sería true si todas las fuentes lo son;
cualquier false domina; de otro modo permanece null. No hay declaración automática.

Límites del resultado: 50 000 filas, 200 columnas, 10 MiB del contenido JSON; rechazo sin
truncamiento. Preview no publica datos derivados. Apply guarda contenido completo BLOB,
recibo y diccionario juntos en una transacción SQLite (`derived_content_v2` y
`data_workspace_revisions_v2`), con UNIQUE proyecto/preview. Reintentar devuelve el mismo
recibo publicado, aun si venció el preview; leerlo no lo declara vigente para S04. Fallos
antes del commit revierten todo; reinicio conserva la operación completa o ninguna.
Los originales S03A siguen en filesystem bajo su protocolo de manifiestos: no se afirma
atomicidad entre esos archivos y SQLite ni respaldo/restauración remota. Respaldar DB y
objetos S03A juntos. No se migran ni comparten bases de otros worktrees.
