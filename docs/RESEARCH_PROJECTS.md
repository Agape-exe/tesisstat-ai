# Research — gestión de proyectos (sesión 2, integrante 1)

Implementado en `feat/research-projects`, desde `origin/develop` (`9e1c4ec`). No se
modifican Statistics, contratos compartidos, `backend/app/main.py`, `App.tsx`,
dependencias ni configuración global. No hay procesamiento documental ni IA.

## Ejecutar la demostración

Requisitos y primera instalación: ver README principal. Desde la raíz del repositorio,
en PowerShell, terminal 1:

```powershell
cd backend
uv sync --locked
$env:CORS_ORIGINS = '["http://localhost:5174"]'
uv run uvicorn app.modules.research.dev_app:app --host 127.0.0.1 --port 8001
```

Terminal 2, desde la raíz:

```powershell
cd frontend
npm ci
npx --no-install vite --config src/features/research/vite.demo.config.ts --host 127.0.0.1
```

Abrir **http://localhost:5174/research-demo/**. La aplicación original de sesión 1
puede seguir en 5173/8000. No cambiar sus archivos de entrada.

En bash: `CORS_ORIGINS='["http://localhost:5174"]' uv run uvicorn
app.modules.research.dev_app:app --host 127.0.0.1 --port 8001` (en una línea).
Si se usa `127.0.0.1` en el navegador, agregar `http://127.0.0.1:5174` a los orígenes.

Configuración opcional (variables de entorno; no hace falta editar ejemplos compartidos):

| Variable | Valor predeterminado | Ubicación |
| --- | --- | --- |
| RESEARCH_DB_PATH | `.cache/research/projects.sqlite3` | Backend, ruta relativa a su directorio de ejecución |
| CORS_ORIGINS | `Settings` compartido; sobreescribir con el origen 5174 para la demo | Backend, array JSON de orígenes exactos |
| VITE_RESEARCH_API_BASE_URL | `http://127.0.0.1:8001` | Frontend, establecer antes de arrancar Vite o hacer build |

`ResearchDevSettings` también lee `backend/.env` al ejecutarse desde backend. Las variables
de shell tienen prioridad. No hay secretos, servicios remotos ni nuevos paquetes.

## Datos y comportamiento

Proyecto en **borrador**, separado de `ResearchPackage`. Puede existir sin variables,
hipótesis o dataset. UUID y fechas UTC se generan en el servidor; título, descripción
y datos académicos son editables. El estado permanece `draft`.

| Campo | Validación |
| --- | --- |
| title | Obligatorio, 5–200 caracteres después de recortar espacios |
| description | Opcional, hasta 2000; por defecto cadena vacía |
| university | Obligatorio, 2–160 |
| faculty | Opcional, hasta 160; por defecto cadena vacía |
| program | Obligatorio, 2–160 |
| degree | Obligatorio: bachelor, master, doctorate u other |
| academic_year | Entero estricto 1900–2100 o null; opcional |

El cliente normaliza el formulario y muestra errores junto a cada campo; el servidor
vuelve a validar y rechaza campos desconocidos, IDs/fechas/propietarios aportados por cliente
y tipos inválidos. Una actualización inválida conserva el proyecto existente.

La pantalla incluye carga, listado vacío, error/reintento, detalle, creación, edición y
cancelación. Guardar bloquea nuevos envíos. El diálogo nativo de eliminación admite Escape
o Cancelar, mantiene el foco dentro y lo devuelve al botón de origen al cancelar. No se
envía DELETE hasta confirmar. Los fallos conservan el formulario o diálogo para reintentar.
Las lecturas usan cancelación y los requests tienen un máximo de espera de 10 segundos.

## API de desarrollo

OpenAPI: http://127.0.0.1:8001/docs. Salud: `GET /health`.

| Método y ruta | Respuesta |
| --- | --- |
| POST /api/research/projects | 201, proyecto y cabecera Location |
| GET /api/research/projects | 200, array ordenado por última actualización descendente |
| GET /api/research/projects/{id} | 200, proyecto |
| PUT /api/research/projects/{id} | 200, reemplazo completo de datos editables |
| DELETE /api/research/projects/{id} | 204, sin cuerpo |

Errores: 404 para proyecto inexistente; 422 para datos/UUID/JSON inválidos; 503 para
fallos de SQLite durante una operación. Formato: `{ "detail": "Mensaje comprensible",
"errors": { "campo": "Mensaje" } }` (errors solo en validación).

Ejemplo completamente ficticio:

```json
{
  "title": "Estudio ficticio sobre hábitos de aprendizaje",
  "description": "Proyecto sintético para desarrollo.",
  "university": "Universidad de Demostración",
  "faculty": "Facultad Simulada",
  "program": "Programa Sintético",
  "degree": "bachelor",
  "academic_year": 2026
}
```

## Separación de responsabilidades

`backend/app/modules/research/projects/`:

- `models.py`: modelos locales del borrador/proyecto, sin acoplamiento a FastAPI o SQLite.
- `repository.py`: puerto ProjectRepository.
- `use_cases.py`: crear, listar, consultar, actualizar y eliminar mediante ese puerto.
- `sqlite_repository.py`: adaptador de desarrollo, consultas parametrizadas, transacciones
  y conexión por operación para soportar los hilos de FastAPI.
- `routes.py`: adaptador REST y códigos HTTP.

`backend/app/modules/research/dev_app.py`: composición independiente, errores y CORS CRUD.
`backend/tests/research/test_projects.py`: casos de uso con repositorio en memoria y API
con bases temporales. Ninguna prueba requiere datos reales o servicios externos.

`frontend/src/features/research/projects/`: DTOs locales y puerto ProjectService (`types.ts`),
cliente HTTP (`api.ts`), validación, formulario, diálogo, vista y estilos con prefijo `rp-`.
El servicio se inyecta en ResearchProjects para probar sin API. Se conserva el antiguo
`features/research/service.ts`, que corresponde al contrato metodológico ResearchPackage.

Entradas independientes: `frontend/research-demo/index.html`, `features/research/demo.tsx`
y `features/research/vite.demo.config.ts`. No se modifica el bootstrap global.

## Verificación

Desde backend:

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python -m scripts.export_contracts --check
```

Desde frontend:

```powershell
npm run lint
npm run format:check
npm test
npm run build
npx --no-install vite build --config src/features/research/vite.demo.config.ts
```

El build principal comprueba TypeScript de todo src. El build de la demo genera sus
artefactos en `dist/research-demo/` (ignorado). Para inspeccionarlo:
`npx --no-install vite preview --config src/features/research/vite.demo.config.ts
--host 127.0.0.1 --port 5174`, en una línea, y abrir `/research-demo/`.
Si cambia el origen o la API, configurar las variables antes del build.

Resultados de cierre: **48 pruebas pytest y 33 pruebas Vitest aprobadas**, Ruff,
ESLint, Prettier, TypeScript y ambos builds aprobados. Esquemas compartidos comprobados
sin cambios. La configuración CI compartida se conserva; el build adicional de esta
demo se ejecutó localmente con el comando indicado.

Comprobación manual E2E (31/10/2026): formulario vacío muestra errores y enfoca el título;
crear proyecto sintético → POST 201; editar → PUT 200; recargar → listado GET 200 con
título editado; abrir detalle → GET 200; cancelar eliminación conserva el proyecto y
restaura foco; confirmar → DELETE 204 y listado vacío. SQLite se comprobó con cero
registros restantes. Consola de navegador sin errores. No quedaron datos de esa prueba.

## Límites e integración futura

SQLite es **solo persistencia local de desarrollo**. Sobrevive al reinicio en el mismo
equipo, pero no es persistencia definitiva, backup ni solución para Render Free.
El esquema se crea automáticamente y todavía no tiene migraciones. Las ediciones
concurrentes usan última escritura; no hay versionado optimista ni paginación.

La aplicación de demo **no tiene autenticación ni aislamiento por usuario**: todas las
solicitudes comparten el repositorio local. Ejecutar en loopback y usar información
ficticia. No desplegar esta demo con datos reales. Supabase requerirá adaptador nuevo,
auth verificada, propietario y RLS, migraciones y pruebas de aislamiento.

Para integrar posteriormente, componer `create_router(ProjectService(repository))` desde
la aplicación principal y añadir el origen/métodos CORS acordados. Montar ResearchProjects
en el enrutamiento frontend existente. Esas modificaciones compartidas quedan pendientes
de coordinación; no se hicieron en esta rama. La conversión a ResearchPackage ocurrirá
solo cuando haya metodología suficiente, sin alterar los contratos vigentes.
