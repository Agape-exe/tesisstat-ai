# Archivos, hojas, tablas y contexto C3 — S03A

Implementación local sin proveedores externos. Modelos canónicos en
`app/shared/data_sources_v2.py`; DTOs de entrada estrictos en `sources/models.py`.
Todas las rutas pertenecen a `/api/v2/research/projects/{project_id}` y comprueban el
proyecto y la relación padre/hijo. El actor es `local`, asignado por el composition root;
no es una identidad remota. Conserva las guardas development/loopback y CORS explícito.

## Recursos y operaciones

- GET/POST `/files`: inventario de originales y todas sus hojas. POST recibe bytes con
  `X-File-Name` codificado mediante percent-encoding; 201 solo después de publicar.
- GET `/files/{file_id}/original`: descarga exacta, verificada contra SHA-256.
- PATCH `/files/{file_id}/sheets/{sheet_id}`: `expected_revision` de la hoja y
  `action=exclude|include|extract`. Extract exige `header_row` y `range` rectangular A1
  (p.ej. `{"expected_revision":1,"action":"extract","header_row":3,"range":"A3:B40"}`).
  El rango incluye el encabezado. Se confirma la selección, no el diseño científico.
- GET `/tables`: tablas de hojas incluidas. GET `/tables/{id}` conserva también metadatos
  históricos de una tabla excluida. Excluir no borra bytes/contexto; incluir conserva su ID.
- GET `/tables/{id}/preview`: máximo 20 filas de la extracción completa persistida.
  Una tabla excluida no es una fuente utilizable: lectura de contenido devuelve 409.
- GET/PATCH `/tables/{id}/context`, GET `/tables/{id}/context/revisions`:
  mismas reglas PATCH/CAS/confirmación que C2. GET `/table-contexts` lista contextos actuales
  para nombres comprensibles en el inventario, sin filas. Revisión cero es virtual.

Guardar contexto no exige confirmación. Omitir conserva, null borra, una edición invalida
solo la confirmación del fact cambiado. Confirmar avanza revisión y asigna actor/fecha UTC
por servidor. Se rechazan IDs de columna ajenos, campos extra y fechas/actor del cliente.
No hay objetivos/hipótesis duplicados ni relaciones ejecutables. La UI compara 409 y permite
conservar su borrador sobre la revisión actual sin sobrescribir campos no editados.

La detección XLSX `tabular-v2` exige encabezados únicos, textuales y no vacíos para columnas
con información. Omite columnas completamente vacías dentro del rango y publica sus letras;
conserva datos a ambos lados y coordenadas originales por columna. Una columna con datos
sin encabezado pide aclaración y corrección del original; nunca se descarta silenciosamente.
Encabezados numéricos, celdas combinadas, una única columna, bloques separados por filas, encabezados repetidos,
títulos previos y hojas llamadas instrucciones/resumen piden aclaración. Una tabla de una
columna se admite mediante rango explícito. No se interpreta cualquier diseño libre.
El libro no exige selección hoja por hoja: las claras entran por defecto, incluidas ocultas.
Las hojas vacías quedan pendientes hasta exclusión explícita. Una hoja pendiente no impide
leer las tablas listas. `complete` significa todas listas/excluidas, no revisión humana.

## Valores y límites

Reutiliza validadores/límites de datasets CSV/XLSX. CSV UTF-8: coma o punto y coma, cabeceras
completas y filas con anchura constante; faltante CSV se conserva como `""`, XLSX como null.
Valores se representan como texto/null, sin imputación, inferencia de escala o conversión
de códigos. Texto `0001` conserva ceros; formatos visuales de celdas numéricas no se convierten
en texto con ceros. Fechas disponibles usan ISO; se conservan cadenas y booleanos como texto.
Fórmulas XLSX nuevas se conservan con su cálculo acotado y procedencia, sin caché (C01).
Encabezados con fórmulas requieren corrección/rango válido. CSV y XLSX v1 conservan su lector.

Límites por archivo: 10 MiB, 50 MiB descomprimidos, 1000 entradas ZIP; sin macros/cifrado.
Por hoja/tabla: 50 000 filas de datos y 200 columnas. Por libro: 30 hojas, 150 000 filas
físicas visitadas (incluidos encabezados/blancos), 2 000 000 celdas visitadas y 30 MiB de
JSON materializado entre todas sus tablas, incluidas excluidas. Se lee hasta el final sin
confiar en dimensiones XLSX que podrían esconder filas. Los límites globales también rigen
CSV. Rebasarlos devuelve 413 y no publica ninguna parte de ese archivo. Archivos distintos
se cargan como operaciones independientes; la UI conserva éxitos y permite reintentar fallos.
Las hojas especiales de gráficos se inventarían como pendientes sin observaciones; se pueden
excluir sin perder las otras hojas. No se promete interpretar Excel libre ni trabajar con macros.

## Identidad, hashes y consumo S03B/S04/S06

UUIDs de archivo/hoja/tabla/columna asignados por servidor. Mismos encabezados en dos hojas
no unen identidades. Original inmutable guardado una sola vez. Tabla JSON inmutable con
todos los datos; no una copia del libro por hoja. Su metadato enlaza hash original,
hoja/índice, encabezado/rango, algoritmo, conteos y advertencias. La extracción publicada
no se reedita en sitio: S03B creará derivados con nuevas identidades y recetas.

`sha256-bytes` identifica el original. `table-json-v1` es SHA-256 de UTF-8 JSON compacto
`{"columns":[nombres],"rows":[todas_las_filas]}` con Unicode sin escape y orden fijo de esas
dos claves. El hash de hoja/contexto usa `canonical_hash`/`json-sort-v1`, excluyendo hash propio,
fechas y confirmation. Contexto tiene historial y hash/revisión independientes del contenido.
`compute_dataset_hash` y los seis contratos v1 permanecen intactos.

Puerto local `SourceService.read_table(project_id,table_id)` devuelve metadatos y **todas**
las filas verificadas de esa extracción, exige hoja incluida y no activa datasets v1.
`source_refs` resuelve referencias `source_file`, `source_sheet`, `table` y `table_context`
(solo si hay revisión guardada). El futuro resolver S04 validará revisión/hash esperados,
vigencia de selección y facts confirmados por intención. No usar ID/hash como permiso.
S03B debe crear diccionario a partir de los IDs reales de columna y permitir exploración/
preparación opcional, incluida combinación confirmada por identificadores. S04 permitirá
varios análisis por proyecto con sus fuentes específicas; S06 añadirá consumo por tutor.
El chat, paquetes y motor ejecutable actuales conservan sus fuentes v1.

## Persistencia y recuperación

SQLite: `source_files_v2`, `source_file_revisions_v2`, `imported_tables_v2` y
`table_context_revisions_v2`. Bytes en un directorio hermano del almacén de datasets
configurado, con sufijo `-sources-v2` (p.ej. `datasets-sources-v2`), sin alterar el inventario
legado. Ninguna ruta/clave física se acepta o devuelve en contratos.

Pasos: carga acotada → inventario/extracción completa → manifiesto local pendiente con
IDs/hashes → escritura exclusiva, flush/fsync y verificación de objetos → transacción
SQLite de publicación → retirar manifiesto. CAS de selección/contexto usa BEGIN IMMEDIATE.
Un error ordinario revierte la transacción y elimina solo objetos recién creados; nunca
anuncia 201/200 con tablas faltantes. Tras interrupción antes del commit pueden quedar
huérfanos, sin metadatos visibles. Después del commit el manifiesto puede seguir pendiente;
su recuperación conserva los objetos publicados y verifica sus hashes. No se promete
atomicidad entre SQLite y filesystem, tolerancia a pérdida eléctrica del disco, backup,
persistencia remota ni recuperación de un objeto referenciado que fue borrado externamente.
Falta/corrupción de objetos devuelve 503, sin tratarla como ausencia de datos.

Detener **esa instancia** antes del mantenimiento, respaldar su DB y directorio juntos.
Desde backend, inspeccionar con:

```powershell
python -m scripts.recover_source_imports --db RUTA_A_PROJECTS_SQLITE3 --storage RUTA_A_SOURCES_V2
```

Después de revisar, repetir con `--apply`: elimina solo objetos UUID del manifiesto sin
referencia en esa DB; conserva y verifica publicados; retira el manifiesto. No limpia
automáticamente al arrancar ni toca archivos de otra instancia. Una DB/directorio
inconsistentes exigen restaurar juntos su copia, no fabricar registros. El borrado de un
proyecto vuelve inaccesible su árbol; esta entrega conserva sus bytes y revisiones locales,
sin introducir borrado permanente ni política nueva de retención.

## Consumidor S03B integrado

[Data workspace](../data_workspace/README.md) consume estas extracciones sin importarlas por
v1. Expone DatasetRefV2 table_json, diccionario, perfil completo y preparación opcional,
incluida combinación exacta uno a uno. Conserva las rutas/metadatos/originales anteriores;
`WorkspaceService.read_table` amplía el puerto de lectura a derivados y valida todos los
padres. La creación de derivados no escribe objetos sobre las fuentes S03A.


## C01: cálculo local y reimportación

`excel-subset-1` interpreta tokens con gramática cerrada y resultados IEEE-754 finitos.
No usa eval/exec, IA, Excel, LibreOffice, caché ni carga de complementos. Soporta números
literales, signos unarios, + - * /, paréntesis, A1/$A$1 y rangos rectangulares; referencias
a otras hojas del mismo libro (nombres entre comillas y apóstrofos escapados incluidos).
Funciones XLSX en inglés: AVERAGE, SUM, MIN, MAX y COUNT sobre números/referencias/rangos.
En rangos se ignoran texto, booleanos y blancos para agregados, sin modificar los datos.
AVERAGE/MIN/MAX/SUM sin números dan NO_NUMBERS (decisión conservadora; SUM vacío no se
convierte en cero); COUNT devuelve su recuento real. Aritmética sobre blancos o texto
produce VALUE; no se coacciona un faltante a cero ni texto numérico a cantidad. Fechas
referenciadas no se calculan en este subconjunto. No hay redondeo visual de Excel.

Referencias estructuradas: NombreTabla[[#This Row],[columna]] y rangos
NombreTabla[[#This Row],[primera]:[última]]. Las tablas deben tener encabezado y no fila
de totales. Se resuelve por fila física actual dentro del cuerpo de la tabla referida,
incluso en otra hoja, tal como expresa #This Row; esto no demuestra que sean los mismos
sujetos ni une por nombres/IDs. No se presupone orden de estudiantes para análisis pareado.
El cálculo utiliza el original completo, incluidas las hojas pendientes o excluidas de la
vista de tablas; no depende de recortes de importación. Cambiar la selección de hojas
conserva el cálculo inmutable e invalida evidencia según la revisión de archivo existente.
Nombres y columnas se resuelven sin distinguir mayúsculas; caracteres de escape especiales
en encabezados estructurados, otras formas abreviadas @, nombres definidos, matrices,
3D, fechas, potencias, funciones volátiles y el resto de Excel quedan no soportados.

Errores: UNSUPPORTED, REFERENCE, VALUE, SOURCE_ERROR, DIV_ZERO, CYCLE, NON_FINITE,
NO_NUMBERS y LIMIT. Las dependencias propagan errores; jamás se usa un valor previo,
caché o cero para ocultarlos. Marcadores #C01! y advertencias muestran el estado. La
propuesta queda needs_clarification y no se puede aprobar/ejecutar. No se ofrecen esos
errores como categorías. Corrige el original y carga el libro completo nuevamente.

Cotas: 8192 caracteres/fórmula, 1024 tokens, 64 niveles entre celdas, 10000 celdas/rango,
un millón de visitas por libro; más los límites globales existentes. Los excesos quedan
explícitos como LIMIT (sin resultado fiable); el exceso de bytes de materialización
rechaza la publicación completa. No se siguen relaciones externas: solo miembros
xl/tables/ del ZIP para metadatos internos. No se habilitan macros, conexiones o red.

`calculation` forma parte del contenido inmutable verificado por SHA256. GET
/tables/{id}/calculation da toda la auditoría local; preview muestra solo sus fórmulas
visibles. Cada expresión, resultado, código de error, dependencias y tipo original quedan
ligados a libro/hoja/coordenada/versión. El perfil cuenta las fórmulas calculadas y usa
sus mismos valores. Derivados mantienen linaje a las fuentes sin editar su auditoría.

POST /files/{id}/reimport y el botón Reimportar original con cálculo actual crean una
importación nueva desde los bytes originales guardados. No corrigen un original con
fórmulas no soportadas: en tal caso edítalo externamente y vuelve a cargarlo. Nuevos IDs,
variables por revisar y reimported_from explícito; no reemplazan tablas ni análisis,
ni copian contexto/confirmaciones sin revisión. Los históricos mantienen su política;
abrirlos o reiniciar la API nunca vuelve a evaluar fórmulas.
