# TesisStat AI

Para el siguiente trabajo rigen los acuerdos de S00 del 9 de noviembre de 2026:
[alcance y sesiones](docs/ALCANCE_Y_SESIONES.md),
[evolución de contratos](docs/CONTRATOS_EVOLUCION.md) e
[integración y trabajo paralelo](docs/INTEGRACION_PARALELA.md).
El [informe S00](docs/sesiones/S00.md) registra los acuerdos y el
[informe S01](docs/sesiones/S01.md) documenta la creación mínima y el nuevo Inicio.
S02 implementa contexto persistente y S03A incorpora archivos/hojas/tablas y contexto por tabla.
S03B añade diccionario, perfil completo y preparación/combinación opcional de esas tablas.
S02B añade **Completar con ayuda de otro chat** en Contexto: prompt maestro, respuesta
estructurada, revisión editable y aplicación seleccionada sin credenciales ni llamadas IA.
El formulario manual sigue disponible. [Entrega y pruebas S02B](docs/sesiones/S02B.md).
Contexto describe la investigación general; qué representa cada fila se define en Datos
para cada tabla. Relaciones y comparaciones se revisarán por análisis en S04. El prompt 1.1
conserva relaciones narrativas y no impone una clasificación global ni una prueba unilateral.
S04–S06 incorporan análisis por intención, instrumentos/puntuaciones, tutor contextual y
resultados e informes v2. [Entrega y verificaciones S06](docs/sesiones/S06.md).

Demostración local para conectar metodología revisada y datos de un proyecto con un
análisis estadístico persistido. React/TypeScript/Vite y FastAPI/Python 3.12 con SQLite.

La aplicación principal permite recorrer **Contexto → Cargar datos → Revisar datos →
Revisar propuesta → Aprobar y ejecutar → Comprender resultados**, sin documento ni hipótesis
obligatorios y con ayuda contextual opcional. Ofrece descarga TXT/DOCX/PDF de resultados
aprobados, completados y vigentes. El recorrido documental v1 se conserva como herramienta
secundaria. Su motor cubre descriptiva,
asociación, comparaciones paramétricas y no paramétricas, regresión/ANCOVA y sus métricas,
supuestos y advertencias reproducibles. Las 19 técnicas del catálogo están conectadas al flujo
de propuesta, aprobación y ejecución; las conclusiones se limitan explícitamente cuando una
distribución o condición no permite determinar significancia.

Esta es una demostración sin autenticación, exclusivamente local y con información ficticia.
No es un servicio de producción. El recorrido manual completo, las descargas y su revisión
visual fueron confirmados por la usuaria el 2 de noviembre de 2026; consulta los resultados
y límites en [APPLICATION_INTEGRATION.md](docs/APPLICATION_INTEGRATION.md).

## Crear y abrir proyectos

Solo necesitas un **nombre de 1–200 caracteres** (puede ser provisional). La descripción
es opcional, hasta 2000 caracteres. Crear o abrir normalmente un proyecto muestra **Inicio**,
con las seis etapas recomendadas y evidencia de recursos guardados. El proyecto permanece
como borrador; el avance no equivale a completar la investigación ni acredita comprensión.

La navegación principal es **Inicio · Contexto · Datos · Análisis · Resultados**. El chat se
abre desde **Solicitar ayuda** o las herramientas de apoyo. Contexto introduce el recorrido y
conserva documentos/metodología e instrumento; Resultados conserva informes/exportaciones.
Puedes cargar y explorar Datos sin completar Contexto. El contexto manual se guarda y confirma
con revisiones. Análisis v2 utiliza intenciones y tablas concretas con diagnósticos/propuestas;
autorizar datos, aprobar y ejecutar conservan acciones independientes.

API Research: `POST /api/research/projects` acepta `{"title":"Ensayo provisional"}`.
Los datos académicos son opcionales y anulables. El `PUT` existente actualiza **solo campos
suministrados**: omitir conserva; `null` borra universidad, facultad, programa, grado o año.
Nombre y descripción no admiten `null`; nombre vacío o solo espacios produce 422. La UI de
edición envía exclusivamente nombre/descripción y conserva los académicos anteriores.
IDs, fechas de creación y estado se mantienen; el servidor actualiza `updated_at`.

Los enlaces anteriores de assistant/documents/methodology/instrument/reports siguen
abriendo su sección; package conserva su alias a Análisis y los parámetros `view/item`.
Inicio diferencia consultas fallidas de recursos ausentes y permite actualizar su estado.

## Tus datos: archivos y múltiples hojas (S03A)

Datos abre la importación de varios CSV/XLSX, simultáneos o sucesivos. Todas las hojas del
libro se inventarían, incluidas ocultas; las tabulares claras se incorporan automáticamente.
Las demás quedan visibles y pendientes de exclusión o confirmación de encabezado/rango.
Puedes reincorporarlas sin subir el original otra vez. Cada tabla tiene vista previa, conteos
completos y contexto opcional editable, con confirmación explícita y conflicto recuperable.
Los originales se conservan y se pueden descargar con su hash verificado.

Desde **Revisar datos y variables** puedes calcular un perfil completo por tabla, guardar
un diccionario parcial y confirmar sus campos. En **Preparar o combinar (opcional)** puedes
crear derivados o combinar antes/después por identificador exacto, con conteos, vista previa
y confirmación humana. Originales intactos; ningún aviso transforma datos automáticamente.
No necesitas contexto, documento ni hipótesis para explorar, ni limpiar para continuar.
Las herramientas v1 de perfil/preparación
permanecen bajo **Herramientas anteriores de datasets**; sus rutas siguen vigentes y XLSX v1
continúa leyendo solo la primera hoja. Abrir una tabla v2 no cambia el dataset activo v1.
El tutor v2 resuelve tablas/diccionarios/perfiles seleccionados; no mezcla sus resultados.

Ejemplos: [Excel sintético](fixtures/data/s03a/mediciones-sinteticas.xlsx) y
[CSV independiente](fixtures/data/s03a/medicion-independiente.csv). Desde backend,
`python -m scripts.create_s03a_examples` los regenera de forma reproducible.
API, límites y recuperación: [fuentes C3](backend/app/modules/research/sources/README.md).
Pruebas y evidencia visual: [S03A](docs/sesiones/S03A.md) y [S03B](docs/sesiones/S03B.md).
Ejemplos antes/después y claves problemáticas: `fixtures/data/s03b/`.
[API, persistencia y recursos para S04](backend/app/modules/research/data_workspace/README.md).
Las propuestas y ejecución v2 utilizan estas tablas y el mismo selector C4–C5 desde los
formularios y la ayuda del tutor. El análisis v1 conserva su recorrido. Inicio muestra
evidencia y pendientes reales al volver de Datos.

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

S02 permite guardar contexto manual desde **Contexto** con solo una pregunta u objetivo,
sin documento, dataset ni hipótesis. Guardar y confirmar son acciones separadas; el servidor
conserva revisiones y detecta ediciones concurrentes. Inicio consulta el contexto real y
permite continuar a Datos aunque esté incompleto. Documentos y metodología v1 siguen como
apoyo opcional; los recursos v1 conservan sus consumidores y rutas anteriores.
Consulta [S02](docs/sesiones/S02.md), [API C2](backend/app/modules/research/context/README.md)
y [contratos v2](contracts/v2/README.md). Análisis v2 puede proponer, aprobar y ejecutar
una intención descriptiva con datos revisados, sin inventar documento ni hipótesis.

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
externos y entornos distintos de desarrollo. Los resultados y visualizaciones requieren plan
aprobado, resultado vigente y, para datos no sintéticos, autorización explícita enlazada a
proyecto, paquete, dataset y versión. Las figuras de asociación, residuos, grupos y pares se
limitan a 2 000 observaciones mediante muestreo determinista y no existe un endpoint genérico
para exponer datasets. Un p-valor representado como cero no debe describirse como probabilidad
exactamente nula.
El PDF es un informe textual paginado con WinAnsi; los
caracteres fuera de esa codificación se sustituyen con aviso, y DOCX conserva Unicode.
Los resultados históricos se pueden consultar, pero no exportar ni volver a ejecutar con
fuentes desactualizadas. Las sesiones anteriores están documentadas en `docs/` como antecedentes;
los comandos vigentes de demostración y validación están en esta guía. La matriz de cierre y sus
limitaciones se encuentran en [STATISTICS_INTEGRANTE2_AUDIT.md](docs/STATISTICS_INTEGRANTE2_AUDIT.md).

La ayuda del proyecto incluye **Asistente IA**, con conversaciones e historial SQLite.
S06 añade **Ayuda contextual para este paso** y selección explícita de análisis/resultado.
El envío v2 requiere Cloudflare configurado y permiso revocable `tutor_context_v3`; el permiso
anterior no basta. Solo se envían temas, estados y agregados pertinentes: texto libre, nombres,
categorías, documentos y filas permanecen locales. Las explicaciones IA son borradores revisables,
separados de las métricas. Sin proveedor siguen funcionando ayuda estática, historial y formularios.
Resultados permite figuras explícitas e informes TXT/DOCX/PDF, con formato compartido y doble
revalidación de aprobación, autorización y vigencia. [Alcance y pruebas S06](docs/sesiones/S06.md).
Para los antecedentes v1, consulta configuración,
pruebas y limitaciones en [CHAT_CONVERSACIONAL.md](docs/CHAT_CONVERSACIONAL.md).
La Sesión 16A incorporó metodología confirmada, metadatos del dataset, planes y
resultados persistidos, con vigencia y trazabilidad por respuesta. Requiere aceptar
el alcance ampliado del consentimiento. Consulta arquitectura, pruebas y validación
manual en la [guía de contexto de investigación](docs/CONTEXTO_INVESTIGACION_CHAT.md).
La conexión real del chat anterior fue validada por la usuaria; la validación del
contexto ampliado con Qwen3 real queda pendiente. La demo reproducible con proveedor
simulado no necesita credenciales ni realiza solicitudes externas.
