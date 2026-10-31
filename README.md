# TesisStat AI

Sistema multiagente para análisis estadístico de tesis cuantitativas. **Sesión 1: base
compartida**, sin funcionalidades completas de investigación o estadística. Presupuesto S/ 0.
Contexto completo: [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md).

## Requisitos

Git, Python **3.12**, [uv](https://docs.astral.sh/uv/) y Node.js **24** con npm.
Los lockfiles fijan dependencias. Primera instalación requiere conexión; ejecución local y
pruebas no necesitan credenciales ni servicios externos. Ejecutar comandos desde esta carpeta
(el repositorio Git está en `tesisstat-ai/tesisstat-ai` si se abrió su directorio padre).

## Ejecutar localmente

Terminal 1, backend:

```powershell
cd backend
uv sync --locked
Copy-Item .env.example .env
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2, desde la raíz, frontend:

```powershell
cd frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

Abrir [http://localhost:5173](http://localhost:5173). La pantalla debe mostrar
`Backend conectado · API v0.1.0`. Salud: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).
OpenAPI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
En macOS/Linux usar `cp .env.example .env`.

`CORS_ORIGINS` es un array JSON de orígenes exactos (sin barra final). Si se abre la web con
`127.0.0.1`, agregar `"http://127.0.0.1:5173"` al array en `backend/.env`. Reiniciar backend
al cambiar configuración; reiniciar Vite al cambiar `VITE_API_BASE_URL`. El cliente tiene
un tiempo máximo de espera de 8 segundos y permite reintentar. Variables `VITE_*` son públicas:
nunca poner claves privadas allí. Los demás campos de `.env.example` pueden permanecer vacíos.

## Estructura

```text
frontend/
  src/
    app/                        # Pantalla inicial y sus pruebas
    features/research/          # Puerto frontend + mock del módulo 1
    features/statistics/        # Puerto frontend + mock del módulo 2
    shared/api/                 # Cliente de salud
    shared/contracts/generated/ # Tipos TS generados desde JSON Schema
  scripts/                      # Generador de tipos
backend/
  app/
    main.py                     # Composición de la API y GET /health
    core/                       # Configuración de entorno
    modules/research/           # Puertos, responsabilidad integrante 1
    modules/statistics/         # Puertos, responsabilidad integrante 2
    orchestration/agents/       # Tres agentes reservados, sin implementación
    shared/                     # Contratos, puertos externos, adaptadores y fixtures
  scripts/                      # Exportación de JSON Schema
  tests/                        # Salud, CORS, contratos e intercambio de módulos
contracts/v1/                   # Seis esquemas y ejemplos JSON
fixtures/                       # Metodología, datasets y respuestas sintéticas
docs/                           # Contexto del proyecto y decisiones
.github/workflows/ci.yml         # Verificaciones reproducibles
```

Los paquetes Python usan namespace packages. No se crean carpetas vacías: las capas de
dominio, casos de uso y rutas se agregarán a cada módulo cuando tengan código. Los módulos
consumen contratos y puertos; no importan implementaciones internas del compañero.

## Contratos y trabajo independiente

Contratos v1: `ResearchPackage`, `ResearchHypothesis`, `ResearchVariable`,
`DatasetReference`, `AnalysisPlan`, `AnalysisResult`. Fuente canónica en Pydantic;
JSON Schema y TypeScript generados. Ver [contracts/README.md](contracts/README.md) para
campos, versionado y regeneración; [fixtures/README.md](fixtures/README.md) para usar mocks.

Integrante 1 puede usar planes/resultados fixture para construir Research. Integrante 2
puede usar ResearchPackage fixture para construir Statistics. Los mocks se inyectan mediante
puertos; no hay APIs ficticias montadas en producción ni llamadas a proveedores externos.
Los adaptadores Cloudflare/Supabase son esqueletos y fallan explícitamente con
`NotImplementedError` si se invocan; la salud no depende de ellos.

## Pruebas y calidad

Desde `backend/`:

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python -m scripts.export_contracts --check
```

Desde `frontend/`:

```powershell
npm run lint
npm run format:check
npm test
npm run build
```

Formatear con `uv run ruff format .` o `npm run format`. Tras cambiar contratos,
regenerar esquemas desde backend y tipos con `npm run contracts:generate` desde frontend.
CI detecta divergencias y ejecuta las mismas comprobaciones. El build no incluye fixtures
ni librerías de cálculo; los fixtures solo se importan en pruebas.

## Alcance y siguientes pasos

No se implementan aún autenticación, carga/extracción documental, análisis, gráficos,
informes ni despliegue. LangGraph, Plotly, Supabase y librerías estadísticas se incorporarán
cuando sean necesarios. No se han creado recursos de pago ni cargado datos reales.

1. **Integrante 1:** proyectos y persistencia con aislamiento por usuario; validación y carga
   acotada de archivos; extracción metodológica revisable; exploración y preparación de datos.
2. **Integrante 2:** catálogo verificado y criterios de elegibilidad; planificación según
   metodología; motor determinista con pruebas de referencia; después gráficos e informes.
3. **Ambos:** acordar cambios de contratos, integrar Auth/RLS y almacenamiento; definir
   presupuestos de memoria, archivos, concurrencia y tokens antes del despliegue gratuito.

Trabajo en `chore/bootstrap-foundation`; no push ni PR en esta sesión. Verificar las cuotas
vigentes de los proveedores antes de desplegar; no se garantiza capacidad de sus planes gratuitos.
