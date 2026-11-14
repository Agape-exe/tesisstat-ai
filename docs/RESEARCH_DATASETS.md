# Research — datasets locales (sesión 8)

## Funcionalidad y diseño

Cada proyecto puede tener varios datasets CSV/XLSX. El estudiante puede subirlos,
consultar metadatos, previsualizar hasta 20 filas, seleccionar uno como activo y
eliminarlos tras confirmar. El detalle de Research incluye la sección «Datasets».
El módulo `backend/app/modules/research/datasets/` separa modelo, puerto,
lectores, casos de uso, adaptador SQLite y rutas. No se modifican Statistics ni
los seis contratos compartidos.

## Formatos, límites y reglas

- CSV: solo UTF-8, con o sin BOM. Se admiten coma y punto y coma; el delimitador
  se determina según la cantidad de campos de la cabecera. Se preservan valores,
  saltos de línea y comillas conforme a `csv` estándar. No se reemplazan bytes
  inválidos. La cabecera debe estar completa y sin duplicados; cada fila debe
  tener la misma cantidad de campos.
- XLSX: `openpyxl` en modo `read_only`, sin enlaces externos y con
  `data_only=False`. Se usa **la primera hoja del libro**. Las celdas vacías
  aparecen como `null`; fechas se muestran en ISO y otros valores como texto.
  Las fórmulas se muestran como texto con advertencia; no se ejecutan ni se
  presentan resultados calculados. No se admiten XLS, XLSM ni macros.
- Valores iniciales configurables mediante `RESEARCH_DATASET_MAX_BYTES`
  (10 MiB), `RESEARCH_DATASET_MAX_ROWS` (50 000),
  `RESEARCH_DATASET_MAX_COLUMNS` (200), `RESEARCH_DATASET_PREVIEW_ROWS`
  (20) y `RESEARCH_DATASET_MAX_ZIP_BYTES` (50 MiB). Hay además un máximo
  de 1000 entradas ZIP. La API lee la subida por fragmentos y la corta al
  superar el límite.
- Se valida proyecto, pertenencia, extensión y contenido, nombre visible,
  estructura, dimensiones y errores de lectura. No hay limpieza ni cambios
  estadísticos silenciosos. React representa los valores como texto.

## Persistencia y API

Metadatos y vista previa se guardan en SQLite junto al proyecto. Los bytes se
guardan en `RESEARCH_DATASETS_PATH` (por defecto `.cache/research/datasets`)
con nombres UUID; no se expone la ruta al cliente. El índice único de SQLite
permite un solo activo por proyecto. La elección sobrevive al reinicio. El
borrado de proyecto elimina los archivos y metadatos de sus datasets.

| Método | Ruta relativa a `/api/research/projects/{project_id}/datasets` | Resultado |
| --- | --- | --- |
| POST | `/` | 201, metadatos; cuerpo `application/octet-stream`, nombre en `X-File-Name` codificado |
| GET | `/` | 200, lista |
| GET | `/{dataset_id}` | 200, metadatos |
| GET | `/{dataset_id}/preview` | 200, cabeceras, filas y totales |
| POST | `/{dataset_id}/activate` | 200, activo |
| DELETE | `/{dataset_id}` | 204 |

Los errores usan 404 para recursos inexistentes o ajenos, 422 para carga
inválida y 503 para fallos del almacenamiento. `DatasetService.read` es una
interfaz controlada para leer por ID en sesiones futuras. El dataset activo
contiene los campos necesarios para construir un `DatasetReference` con clave
opaca, sin cambiar el contrato; la conversión aún no está implementada.

## Demo y pruebas

En `backend`: `uv sync --locked`, configurar
`$env:CORS_ORIGINS = '["http://localhost:5174"]'` y ejecutar
`uv run uvicorn app.modules.research.dev_app:app --host 127.0.0.1 --port 8001`.
En `frontend`: `npm ci` y
`npx --no-install vite --config src/features/research/vite.demo.config.ts --host 127.0.0.1`.
Abrir `http://localhost:5174/research-demo/`, crear un proyecto ficticio y
usar la sección Datasets. Usar exclusivamente datos sintéticos.

Las pruebas automatizadas cubren formatos, límites, persistencia, selección,
pertenencia, previsualización y flujo React. Ejecutar `uv run --locked pytest`,
`uv run --locked ruff check .`, `uv run --locked ruff format --check .`,
`uv run --locked python -m scripts.export_contracts --check`, `npm test`,
`npm run lint`, `npm run format:check`, `npm run build` y build de demo.

## Limitaciones

SQLite y archivos locales son solo para desarrollo; no hay autenticación,
backup ni migraciones. Un corte durante el borrado puede dejar un archivo
temporal que requiera limpieza manual. No se ofrecen EDA, gráficos ni
preparación estadística. La vista previa conserva como máximo 20 filas en
SQLite y nunca envía el archivo completo al navegador.
