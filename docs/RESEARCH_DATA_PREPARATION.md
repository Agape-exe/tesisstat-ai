# Preparación de datasets Research

La preparación es una acción explícita sobre un dataset existente. EDA sigue siendo diagnóstico y no ejecuta transformaciones. El original conserva sus bytes y metadatos. Cada confirmación crea un CSV UTF-8 con un ID nuevo y `source_dataset_id`; el usuario decide por separado si lo activa.

## Arquitectura y reglas

`backend/app/modules/research/preparation/` contiene modelos, motor determinista, caso de uso, puerto, repositorio SQLite y rutas. El motor usa `iter_dataset` y los límites existentes: 10 MiB, 50 000 filas, 200 columnas y 50 MiB descomprimidos para XLSX. Se admiten hasta 20 operaciones por plan, en el orden indicado. Las referencias a columnas se validan contra el resultado de las operaciones previas. No se ejecuta código del archivo ni se envían datos a IA.

Operaciones: eliminar duplicados exactos conservando la primera fila; eliminar filas con faltantes en columnas seleccionadas; reemplazar faltantes por una constante; eliminar columnas seleccionadas; renombrar una columna; quitar espacios externos; convertir una columna a numérico mediante `Decimal`. La conversión rechaza fechas, categorías no numéricas y valores no finitos; advierte si cambia ceros iniciales. Eliminar columnas con nombres que parecen identificadores genera una advertencia. Se impide eliminar todas las columnas.

Los faltantes se deciden en cada operación: `empty_is_missing` incluye celda nula, vacía y espacios; `missing_markers` puede incluir `NA`, `N/A`, `null` y `none` sin distinguir mayúsculas. Por defecto los marcadores textuales no se consideran faltantes. La política queda dentro del plan registrado. Una celda nula de XLSX se serializa como campo CSV vacío. Los valores que podrían interpretarse como fórmulas en CSV se rechazan, sin modificación silenciosa. Los XLSX con fórmulas en celdas de datos se rechazan para preparación.

## Vista previa y confirmación

`POST /api/research/projects/{project_id}/datasets/{dataset_id}/preparation/preview` recibe `{ "operations": [...] }`. Lee el dataset completo y devuelve métricas antes y después, resumen por operación, advertencias, hasta 20 filas, hash del plan, hash del origen, ID de vista previa y vencimiento a 15 minutos. La vista previa se guarda solo como metadatos de control; no crea un archivo derivado.

`POST /api/research/projects/{project_id}/datasets/{dataset_id}/preparation/apply` recibe `{ "plan": {"operations": [...]}, "preview_id": "...", "plan_hash": "...", "confirm": true }`. Verifica proyecto, dataset, plan, vigencia y contenido fuente; repite el mismo motor. Un reintento con el mismo ID devuelve el derivado ya creado. Un plan cambiado, vista vencida o contenido modificado devuelve 409. La validación de solicitud y operaciones inválidas devuelve 422; recursos inexistentes, 404; fallos de almacenamiento, 503.

`GET /api/research/projects/{project_id}/datasets/{dataset_id}/preparations` consulta el historial de derivados directos. Cada registro contiene origen y resultado, fecha, plan y parámetros, hashes, versión de reglas, conteos y advertencias, sin filas completas. Un derivado puede servir de origen de otro, creando una cadena sin ciclos. La eliminación individual de un dataset con derivados devuelve 409; se eliminan primero sus descendientes. La eliminación del proyecto recorre los datasets del más nuevo al más antiguo. EDA del derivado se calcula de forma independiente cuando se solicita.

## Persistencia y límites

SQLite guarda los controles de vista previa y el historial. La creación del archivo y los dos registros SQLite usa una transacción con bloqueo de escritura y elimina el archivo si la transacción falla. SQLite y el sistema de archivos no ofrecen una transacción distribuida: un cierre abrupto entre escribir el archivo y confirmar puede dejar un archivo huérfano, pero no un dataset visible incompleto. El CSV generado se relee y valida antes de persistirlo. Para evitar errores de exportación, cualquier valor o encabezado con posible interpretación como fórmula se rechaza.

Las vistas previas vencidas que nunca se aplicaron se limpian al crear nuevas vistas previas. Al eliminar un dataset se eliminan sus controles de vista previa y, si era un derivado, su registro de preparación; los descendientes deben eliminarse antes.

## Demo y verificación

En la demo Research, sube un CSV/XLSX sintético, consulta EDA, abre **Preparar datos**, agrega y ordena operaciones, configura columnas y faltantes, pulsa **Previsualizar cambios** y revisa métricas y muestra. Pulsa **Confirmar y crear dataset preparado** para obtener un nuevo dataset. El nuevo elemento aparece en la lista y solo se activa al pulsar **Seleccionar como activo**.

Desde `backend`: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run python -m scripts.export_contracts --check`. Desde `frontend`: `npm test`, `npm run lint`, `npm run format:check`, `npm run build`, `npx vite build --config src/features/research/vite.demo.config.ts`.

La advertencia de columnas metodológicas se limita por ahora a nombres que parecen identificadores; no interpreta textos metodológicos. Los datasets resultantes tienen IDs opacos, estado activo y procedencia, que podrán usar DatasetReference y ResearchPackage en sesiones posteriores. Esos contratos no se modifican aquí.
