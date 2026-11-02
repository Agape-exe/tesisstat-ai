# Research — documentos locales (sesión 4)

## Funcionalidades

Cada proyecto de Research permite adjuntar PDF y DOCX, consultar nombre, formato, tamaño y fecha de carga, y eliminar documentos tras confirmar. Los archivos y metadatos sobreviven al reinicio local. Al eliminar un proyecto desde la demo también se eliminan sus documentos.

El límite es 10 MiB por archivo. El servidor lee el cuerpo por fragmentos y corta al superar el límite. Rechaza archivos vacíos, extensiones distintas, PDFs sin cabecera y cierre básicos y DOCX sin ZIP íntegro y entradas esenciales. No ejecuta ni extrae contenido. Los archivos se guardan bajo identificadores UUID internos; solo se conserva el nombre visible, sin ruta aportada por cliente. Las pruebas usan contenido sintético.

## Archivos principales

- `backend/app/modules/research/documents/`: modelo, puerto, casos de uso, rutas y adaptador local.
- `backend/app/modules/research/dev_app.py`: composición y errores HTTP.
- `backend/tests/research/test_documents.py`: pruebas de carga, validación, reinicio, eliminación y fallos.
- `frontend/src/features/research/documents/`: cliente HTTP, vista y pruebas.
- `frontend/src/features/research/projects/ResearchProjects.tsx`: sección dentro del detalle.

## Endpoints

| Método | Ruta | Respuesta |
| --- | --- | --- |
| POST | `/api/research/projects/{project_id}/documents` | 201, metadatos |
| GET | `/api/research/projects/{project_id}/documents` | 200, lista |
| DELETE | `/api/research/projects/{project_id}/documents/{document_id}` | 204 |

El POST recibe los bytes directamente como `application/octet-stream` y el nombre codificado con `encodeURIComponent` en `X-File-Name`; no usa multipart. Los errores retornan `{ "detail": "..." }`: 404 si no existe el proyecto o documento, 422 si el archivo es inválido y 503 si falla el almacenamiento. Los metadatos incluyen `id`, `project_id`, `name`, `format`, `size` (bytes) y `uploaded_at` (UTC).

## Ejecución local

Desde la raíz, en PowerShell, terminal 1:

```powershell
cd backend
uv sync --locked
$env:CORS_ORIGINS = '["http://localhost:5174"]'
uv run uvicorn app.modules.research.dev_app:app --host 127.0.0.1 --port 8001
```

Terminal 2:

```powershell
cd frontend
npm ci
npx --no-install vite --config src/features/research/vite.demo.config.ts --host 127.0.0.1
```

Abrir `http://localhost:5174/research-demo/`. Crear o abrir un proyecto ficticio y usar la sección «Documentos». Solo ejecutar esta demo en loopback. Si se abre Vite con `127.0.0.1`, agregar ese origen a `CORS_ORIGINS`.

Rutas configurables mediante `RESEARCH_DB_PATH` (por defecto `.cache/research/projects.sqlite3`) y `RESEARCH_DOCUMENTS_PATH` (por defecto `.cache/research/documents`), relativas al directorio de ejecución del backend. `.cache/` está excluida de Git.

## Pruebas

```powershell
cd backend
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m scripts.export_contracts --check
cd ../frontend
npm test
npm run lint
npm run format:check
npm run build
npx --no-install vite build --config src/features/research/vite.demo.config.ts
```

## Limitaciones

El almacenamiento es solo de desarrollo, sin autenticación, backup, migraciones ni aislamiento entre usuarios. No desplegar públicamente ni cargar tesis reales. La validación detecta estructura básica, no garantiza que un lector pueda abrir todos los PDFs/DOCX ni realiza análisis antivirus. La operación de archivo y SQLite no constituye una transacción distribuida; un corte del proceso durante la escritura o eliminación puede requerir limpieza manual de archivos huérfanos. No hay descarga, vista previa ni extracción de texto.
