# ResearchPackage v1.0.0

## Funcionalidad y arquitectura

La sección **Preparar investigación para análisis** del detalle de Research deja seleccionar un documento con revisión humana confirmada, el dataset activo y sus vínculos. El usuario declara la procedencia sintética del dataset original y confirma columnas, roles, escalas, objetivos, variables de cada hipótesis, tipo y dirección. Puede validar antes de construir. El paquete se valida con `app.shared.contracts.ResearchPackage`; no se modificaron los seis contratos compartidos ni Statistics.

`packages/models.py` define solo configuración local, estado y registro persistido. `PackageService` consulta `ProjectService`, `DocumentService`, `ReviewService` y `DatasetService`; `packages/repository.py` es el puerto de persistencia y `packages/sqlite_repository.py` su adaptador. `packages/reader.py` implementa el puerto de lectura para una integración futura. Las rutas viven en `packages/routes.py`.

## Mapeo de metodología al contrato

El título sale de la revisión confirmada. `methodology_status` es `reviewed`. Cada variable conserva su UUID de revisión; el nombre, dimensiones y preguntas provienen de esa misma revisión. El usuario confirma rol y escala en la configuración; `unknown` es válido y produce una advertencia cuando corresponda. Ningún tipo técnico sugerido por EDA se convierte en escala estadística.

La hipótesis general usa la clave de origen `general`; una específica usa `specific:<índice desde 0>`. Cada una recibe un UUID estable de configuración. Su enunciado procede de la revisión y su objetivo debe seleccionarse literalmente entre el objetivo general o los específicos revisados. Los IDs de variables deben existir y ser únicos dentro de cada hipótesis. `null_statement` solo se incluye si el usuario lo escribe. Tipo, alternativa, diseño y dependencia entre observaciones usan exclusivamente los enumerados del contrato; el valor por defecto es `unknown` o `unspecified`. Las notas de muestreo son texto del usuario, inicialmente vacío.

## DatasetReference y ubicación opaca

El dataset seleccionado debe estar activo y pertenecer al proyecto. El paquete conserva UUID, formato, filas, columnas y el booleano de procedencia. `location` es `research-dataset:<UUID>`; no es una ruta del sistema de archivos ni contiene datos crudos. Un consumidor autorizado debe resolver el UUID dentro de Research: comprobar acceso al proyecto, invocar `DatasetService.get(project_id, dataset_id)` y, para obtener bytes, `DatasetService.read(project_id, dataset_id)`. Esa integración aún no existe en Statistics. El origen preparado se conserva en `Dataset.source_dataset_id`; la clasificación sintética se hereda al crear derivados. Declarar o corregir el origen en el dataset original actualiza explícitamente sus derivados.

## Validaciones y estados

Se comprueban proyecto, revisión confirmada, dataset activo y origen conocido; título, variables e hipótesis no vacíos; fuente exacta de cada vínculo; columnas reales y únicas; objetivos revisados; IDs únicos y referencias válidas. La validación final invoca Pydantic. Errores bloquean la construcción. Advertencias metodológicas se añaden a `pending_questions` y no equivalen a preparación estadística completa.

Los estados son `incomplete`, `warnings`, `ready`, `generated` y `stale`. Una huella SHA-256 de la revisión y otra del contenido y metadatos del dataset detectan cambios. La versión de revisión y la versión de configuración también se guardan. Cambiar la revisión, el dataset o una vinculación deja el paquete previo desactualizado. La reconstrucción exige guardar de nuevo la configuración y revisar los vínculos; nunca se cambian hipótesis o columnas automáticamente.

## Persistencia y concurrencia

SQLite conserva configuración, vínculos, versiones, huellas, fecha de modificación, paquete generado, advertencias y fecha de construcción. Un `UPDATE ... WHERE version = ?` implementa control optimista; un conflicto devuelve 409. El paquete previo se conserva al editar para trazabilidad, pero GET devuelve 409 mientras esté desactualizado. Los archivos se siguen leyendo únicamente mediante `DatasetService`.

## API

| Método | Ruta | Resultado |
| --- | --- | --- |
| GET | `/api/research/projects/{id}/package/status` | Fuentes disponibles, errores, advertencias y estado |
| GET/PUT | `/api/research/projects/{id}/package/configuration` | Lee o guarda configuración con versión |
| POST | `/api/research/projects/{id}/package/validate` | Validación sin generar |
| POST | `/api/research/projects/{id}/package/build` | Construye y valida ResearchPackage |
| GET | `/api/research/projects/{id}/package` | Paquete vigente o 404/409 |
| PUT | `/api/research/projects/{id}/datasets/{dataset_id}/origin` | Declara `{ "synthetic": true/false }` en un original |

## Demo y pruebas

Usar únicamente datos ficticios. Desde `backend`, iniciar `uv run uvicorn app.modules.research.dev_app:app --host 127.0.0.1 --port 8001`. Desde `frontend`, iniciar `npx vite --config src/features/research/vite.demo.config.ts --host 127.0.0.1`; abrir `/research-demo/`. Crear un proyecto ficticio, adjuntar un documento de muestra, confirmar su revisión, subir y activar un CSV ficticio. En la nueva sección seleccionar ambas fuentes, declarar origen, guardar; luego vincular columnas y objetivos, volver a guardar, validar y generar.

Ejecutar `pytest`, `ruff check .`, `ruff format --check .` y `python -m scripts.export_contracts --check` en backend. En frontend, `npm test`, `npm run lint`, `npm run format:check`, `npm run build` y `npx vite build --config src/features/research/vite.demo.config.ts`.

## Limitaciones

La app de desarrollo no tiene autenticación; la integración autorizada del puerto de lectura y la resolución del dataset quedan para la siguiente sesión. Las descripciones metodológicas en lenguaje natural requieren selección humana de diseño y observaciones. `unknown` puede llegar a Statistics con preguntas pendientes; el paquete válido no autoriza por sí solo un plan estadístico.
