# Extracción de texto Research (sesión 5)

La demo local permite abrir un documento PDF/DOCX ya adjuntado, consultar su extracción guardada y solicitar la extracción. Los resultados se conservan en SQLite para su uso futuro por Research Understanding Agent. Una extracción completada o sin texto se devuelve desde caché; una fallida puede reintentarse. Al eliminar el documento o proyecto, también se elimina el resultado.

## Implementación

- `backend/app/modules/research/documents/extraction.py`: modelos, puertos, caso de uso y adaptadores locales `pypdf` y `python-docx`.
- `backend/app/modules/research/documents/sqlite_repository.py`: lectura por IDs internos y tabla `research_extractions`.
- `backend/app/modules/research/documents/routes.py`: rutas HTTP.
- `frontend/src/features/research/documents/`: consulta, acción y vista previa.
- `backend/tests/research/test_extraction.py`: archivos generados y ficticios.

Las bibliotecas son `pypdf` 6.x y `python-docx` 1.2.x, fijadas en `backend/uv.lock`. No se ejecutan macros ni se envía contenido a servicios externos.

## API

- `POST /api/research/projects/{project_id}/documents/{document_id}/extract`: extrae o devuelve un resultado guardado.
- `GET /api/research/projects/{project_id}/documents/{document_id}/extraction`: devuelve el resultado guardado; 404 si no existe, el documento no pertenece al proyecto o el proyecto no existe.

El resultado contiene IDs, `status` (`completed`, `no_text`, `failed`), `text`, `character_count`, `units_processed`, `processed_at`, `warnings` y `truncated`. Errores de lectura se expresan con mensajes públicos genéricos. Un PDF sin texto seleccionable indica que requiere OCR.

## Límites y seguridad

La carga existente limita cada archivo a 10 MB y los DOCX a 50 MB descomprimidos durante su validación. La extracción limita por defecto a 100 páginas PDF, 10 000 unidades DOCX, 200 000 caracteres y 20 MB de contenido descomprimido por página PDF. Los límites se configuran mediante `RESEARCH_EXTRACTION_MAX_PAGES`, `RESEARCH_EXTRACTION_MAX_UNITS`, `RESEARCH_EXTRACTION_MAX_CHARACTERS` y `RESEARCH_EXTRACTION_MAX_CONTENT_BYTES` en la app de desarrollo. El texto es contenido no confiable: se presenta como texto, sin interpretar HTML. Los resultados viven en `.cache/`, excluida de Git.

No hay OCR ni extracción de texto de imágenes. El orden de lectura PDF depende de la estructura interna del archivo. El procesamiento es síncrono y la demo no tiene autenticación; no debe exponerse públicamente.

## Prueba local

Desde `backend`: `uv run uvicorn app.modules.research.dev_app:app --reload --host 127.0.0.1 --port 8001`. Desde `frontend`: `npm run dev -- --config src/features/research/vite.demo.config.ts`. En la demo, crea un proyecto, adjunta un PDF/DOCX ficticio, pulsa **Ver extracción** y luego **Extraer texto**.

Verificaciones: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run python -m scripts.export_contracts --check`; en frontend, `npm test`, `npm run lint`, `npm run format:check`, `npm run build` y `npm run build -- --config src/features/research/vite.demo.config.ts`.
