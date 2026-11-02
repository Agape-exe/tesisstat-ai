# TesisStat AI

Demostración local para conectar metodología revisada y datos de un proyecto con un
análisis estadístico persistido. React/TypeScript/Vite y FastAPI/Python 3.12 con SQLite.

La aplicación principal permite recorrer **Proyecto → Documento → Metodología → Dataset →
EDA → Preparación → ResearchPackage → Propuesta → Aprobación → Ejecución → Resultados**,
con descarga DOCX/PDF de resultados completados y vigentes. Los cálculos integrados son
resumen descriptivo y Pearson. Las demás técnicas del catálogo tienen adaptadores pendientes.

Esta es una demostración sin autenticación, exclusivamente local y con información ficticia.
No es un servicio de producción. El recorrido manual completo, las descargas y su revisión
visual fueron confirmados por la usuaria el 2 de noviembre de 2026; consulta los resultados
y límites en [APPLICATION_INTEGRATION.md](docs/APPLICATION_INTEGRATION.md).

## Iniciar la aplicación

Requisitos: Git, Python **3.12**, [uv](https://docs.astral.sh/uv/) y Node.js **24** con npm.
Ejecuta desde el repositorio Git (`tesisstat-ai/tesisstat-ai` si abriste su carpeta padre).

Terminal 1:

```powershell
cd backend
uv sync --locked
# Solo si no existe .env:
Copy-Item .env.example .env
uv run uvicorn app.modules.research.dev_app:app --reload --host 127.0.0.1 --port 8001
```

Terminal 2, desde la raíz:

```powershell
cd frontend
npm ci
# Solo si no existe .env:
Copy-Item .env.example .env
npm run dev
```

Abre [http://localhost:5173/](http://localhost:5173/). API:
[salud](http://127.0.0.1:8001/health) y [OpenAPI](http://127.0.0.1:8001/docs).
Una sola API reúne los servicios del recorrido. `app.main:app` conserva su API base de
salud y no monta los endpoints sin autenticación. No se necesita iniciarla para esta demo.

Si conservas un `.env` anterior, usa `APP_ENV=development` y autoriza el origen exacto de
Vite en `CORS_ORIGINS`. El ejemplo incluye localhost/127.0.0.1 en 5173/5174. El frontend usa
`VITE_RESEARCH_API_BASE_URL=http://127.0.0.1:8001`; reinicia Vite si lo cambias. No pongas
secretos en variables `VITE_*`. La revisión manual no necesita Cloudflare ni credenciales.

## Datos ficticios y demostración

La Sesión 17A integra el chat con un grafo LangGraph local de investigación, planificación
y conversación, con una llamada al proveedor como máximo por turno. Consulta
[la arquitectura y demostración multiagente](docs/ORQUESTACION_MULTIAGENTE.md).
Desde `backend/`, `uv run python -m scripts.demo_multiagent` recorre cuatro escenarios
con fuentes sintéticas y un proveedor simulado, sin consumir Qwen3 ni ejecutar estadísticas.

Desde `backend/`, genera entradas reproducibles:

```powershell
uv run python -m scripts.create_demo_inputs
```

El comando crea un DOCX y un CSV bajo `.cache/application-demo/`. Sigue el recorrido
explicado en [la guía de integración](docs/APPLICATION_INTEGRATION.md), incluyendo la
declaración de origen sintético **antes** de preparar el derivado.

Las demos independientes se conservan en `/research-demo/` y `/statistics-demo.html`.
La de Statistics utiliza fixtures y su API independiente; sus resultados no pertenecen a
los proyectos. No hace falta ese servidor para el recorrido principal.

## Pruebas y calidad

Desde `backend/`:

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python -m scripts.export_contracts --check
uv run python -m compileall -q app scripts tests
```

Desde `frontend/`:

```powershell
npm run lint
npm run format:check
npm test
npm run contracts:generate
npm run build
npm run build:research
```

El build principal incluye los tres puntos de entrada, también la demo Statistics. CI
valida contratos, formato, pruebas y compilaciones. Los seis contratos v1.0.0 permanecen
sin cambios. [Guía de contratos](contracts/README.md), [fixtures](fixtures/README.md) y
[contexto arquitectónico](docs/PROJECT_CONTEXT.md).

## Límites actuales

Sin autenticación, Supabase ni despliegue público. La API de demo rechaza clientes/hosts
externos y entornos distintos de desarrollo. Pearson puede devolver `r`, `n`, `p_value`,
`t_statistic` y `degrees_of_freedom`; el chat solo utiliza las métricas persistidas.
Un p-valor representado como cero no debe describirse como probabilidad exactamente nula.
El PDF es un informe textual paginado con WinAnsi; los
caracteres fuera de esa codificación se sustituyen con aviso, y DOCX conserva Unicode.
Los resultados históricos se pueden consultar, pero no exportar ni volver a ejecutar con
fuentes desactualizadas. Las sesiones anteriores están documentadas en `docs/` como
antecedentes; los comandos vigentes de demostración están en esta guía y en la sesión 14.

El detalle de investigación incluye **4. Asistente IA**, con conversaciones e historial SQLite.
El envío requiere Cloudflare configurado y consentimiento explícito. Consulta configuración,
pruebas y limitaciones en [CHAT_CONVERSACIONAL.md](docs/CHAT_CONVERSACIONAL.md).
La Sesión 16A incorpora metodología confirmada, metadatos del dataset, planes y
resultados persistidos, con vigencia y trazabilidad por respuesta. Requiere aceptar
el alcance ampliado del consentimiento. Consulta arquitectura, pruebas y validación
manual en la [guía de contexto de investigación](docs/CONTEXTO_INVESTIGACION_CHAT.md).
La conexión real del chat anterior fue validada por la usuaria; la validación del
contexto ampliado con Qwen3 real queda pendiente. La demo reproducible con proveedor
simulado no necesita credenciales ni realiza solicitudes externas.
