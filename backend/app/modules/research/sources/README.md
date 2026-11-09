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

La detección `tabular-v1` exige encabezados únicos, textuales, no vacíos y un bloque continuo
con datos. Encabezados numéricos, celdas combinadas, una única columna, bloques separados, encabezados repetidos,
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
Fórmulas XLSX se conservan como fuente textual, con advertencia; no se ejecutan ni se usan
resultados en caché. Encabezados con fórmulas requieren corrección/rango válido.

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
