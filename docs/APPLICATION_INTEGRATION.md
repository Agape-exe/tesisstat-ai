# Integración de la aplicación local

Sesión 14 · 2 de noviembre de 2026 · rama `feat/application-integration`.

## Base Git verificada

Árbol inicialmente limpio. `git fetch origin` actualizó `origin/develop` a `28816d0`.
La Sesión 13 (`461b339` y su conciliación final `be105e4`) está integrada mediante
el PR #16; los merges de los PR #14 (`f776dcd`) y #15 (`33ec482`) son ancestros de
esa base. Se actualizó `develop` por fast-forward y se creó la rama de esta sesión.
No se modificó `main`, no se sobrescribió trabajo ajeno y no se utilizó force push.

## Arquitectura de demostración

- Entrada principal `frontend/src/app/App.tsx`: reutiliza `ResearchProjects`.
- El detalle ofrece tres pasos: documento/metodología; datasets/EDA/preparación;
  paquete/análisis/resultados. Al cambiar de paso se vuelven a consultar las fuentes
  persistidas. Guarda los formularios antes de salir; no hay guardado automático.
- `ProjectDocuments`, `DocumentMethodology`, `ReviewEditor`, `ProjectDatasets`,
  `DatasetEDA`, `DatasetPreparation` y `ProjectPackage` conservan sus formularios reales.
- `ProjectAnalysis` es el único flujo de análisis visible. `ResearchStatisticsPanel`
  delega en él; se retira su antiguo botón de ejecución directa. Se conservan los
  clientes y rutas de compatibilidad; `approve=true` nunca concede aprobación.
- `app.modules.research.dev_app:app` compone Research, el puente, la planificación,
  aprobación, ejecución real, persistencia y exportación en una sola API.
- SQLite y archivos locales permanecen en `backend/.cache/research/` por defecto.
  Los IDs del proyecto delimitan documentos, datasets, planes y resultados.
- `app.main:app` permanece sin endpoints de desarrollo. La API demo exige
  `APP_ENV=development`, cliente loopback y host local, además de los controles
  sintéticos y de vigencia existentes. No se habilitan proxies ni acceso público.

Las demos independientes permanecen: `/research-demo/` y `/statistics-demo.html`.
`npm run build` compila las tres entradas; `npm run build:research` comprueba también
la configuración independiente anterior. Statistics usa sus fixtures con
`app.modules.statistics.dev_app:app`, de forma independiente y en lugar de la API
Research si se utiliza su puerto predeterminado 8001. Ese servidor no se monta ni
se requiere para el recorrido principal. Sus resultados no se presentan como datos
de un proyecto activo.

## Comandos de inicio

Desde la raíz del repositorio, en terminales separadas:

```powershell
cd backend
uv sync --locked
# Crear .env desde .env.example solo si no existe.
uv run uvicorn app.modules.research.dev_app:app --reload --host 127.0.0.1 --port 8001
```

```powershell
cd frontend
npm ci
# Crear .env desde .env.example solo si no existe.
npm run dev
```

Ruta principal: [http://localhost:5173/](http://localhost:5173/).
API: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs).
`VITE_RESEARCH_API_BASE_URL` debe apuntar a esa API. No iniciar `app.main` ni la API
independiente de Statistics para completar este recorrido.

`CORS_ORIGINS` es un array JSON de orígenes exactos. El ejemplo incluye
`http://localhost:5173`, `http://127.0.0.1:5173` y sus variantes 5174 para Research.
Un `.env` antiguo puede sobrescribir estos valores: en la máquina de esta sesión solo
autorizaba localhost:5173, por lo que la navegación se realizó desde ese origen.
No se editaron ni imprimieron credenciales. La metodología manual funciona sin IA.

## Recorrido reproducible con datos ficticios

Desde `backend/`:

```powershell
uv run python -m scripts.create_demo_inputs
```

Se crean `.cache/application-demo/metodologia-sintetica.docx` y
`.cache/application-demo/datos-sinteticos.csv`. El CSV contiene cinco filas, con una
duplicada: `(1,2), (2,4), (3,6), (4,8), (4,8)`.

1. Crea una investigación con título, universidad y programa ficticios. Abre su detalle.
2. En Documento y metodología, adjunta el DOCX, abre la extracción y pulsa Extraer texto.
3. Crea metodología manualmente. No autorices llamadas externas a Cloudflare.
4. Edita título, objetivo general, hipótesis general y diseño observacional. Añade las
   variables Horas de estudio (independiente, razón) y Rendimiento (dependiente, razón).
   Guarda el borrador y confirma la revisión. Los campos desconocidos restantes se
   mantienen como pendientes; no se completan con información inventada.
5. En Dataset, sube el CSV y declara su origen Sintético **antes** de preparar datos.
6. Ejecuta EDA: debe identificar cinco filas y un duplicado exacto.
7. Abre preparación, agrega Eliminar duplicados exactos, previsualiza y confirma la
   creación del derivado. El original se conserva. El derivado tiene cuatro filas.
8. Selecciona el derivado como dataset activo. Su origen se hereda del original.
9. En Paquete, selecciona el documento confirmado y el dataset activo. Guarda las
   vinculaciones para cargar la revisión elegida. Usa Actualizar fuentes y estado
   para recargar fuentes guardadas si cambiaste datos desde otro paso.
10. Confirma diseño `observational`, observaciones `independent`, rol y escala `ratio`
    para cada variable; vincula `horas_estudio` y `rendimiento` respectivamente.
11. Vincula la hipótesis general con un objetivo y ambas variables. Elige tipo
    `descriptive` para el primer caso, dirección `two-sided`. Guarda y valida.
12. Genera ResearchPackage. Revisa sus advertencias y aclaraciones.
13. Proponer análisis crea un plan sin aprobación. Revisa técnica, justificación y
    supuestos. Aprobar análisis envía una confirmación del token de esa propuesta.
14. Ejecutar análisis aparece solo después de aprobar. Se usa el dataset del proyecto.
    Sobre el derivado: medias `horas_estudio.mean=2.5` y `rendimiento.mean=5`.
15. Descarga DOCX/PDF desde el resultado completado y vigente.
16. Recarga la aplicación, vuelve a abrir el proyecto y entra a Paquete: se recuperan
    fuentes, paquete, planes, aprobación y resultados de SQLite. La selección del
    paso no se conserva al recargar; los datos y resultados sí.
17. Para Pearson, cambia el tipo a `association`, guarda, valida, genera un paquete
    nuevo, propone, aprueba y ejecuta de nuevo. Resultado esperado: `n=4`, `r=1`.
    No hay p-valor ni afirmación de significancia.
18. Para aclaraciones, usa tipo `unknown`, o asociación con diseño/observaciones
    desconocidos. Se muestra `needs_clarification` y se bloquea aprobar/ejecutar.
19. Para obsolescencia, cambia las notas de muestreo y guarda, o activa otro dataset.
    Actualiza el estado. El resultado anterior sigue visible como histórico, con
    exportación y ejecución bloqueadas. Se necesita nuevo paquete/plan/aprobación.
20. Para errores, intenta un archivo vacío/extensión inválida o Pearson con una
    columna constante. Se muestran errores de entrada o resultado fallido con sus
    advertencias, sin métricas inventadas ni opción de descargar ese fallo.

## Exportación de resultados persistidos

Endpoint GET local:

```text
/api/research/projects/{project_id}/analysis/plans/{plan_id}/results/{result_id}/report.docx
/api/research/projects/{project_id}/analysis/plans/{plan_id}/results/{result_id}/report.pdf
```

Se verifica proyecto existente, plan del proyecto, resultado del plan, dataset y
paquete correspondientes, aprobación explícita, técnica ejecutable, estado completado
y vigencia de fuentes/propuesta. Un cliente no envía métricas ni un AnalysisResult.
La lectura no invoca el motor ni recalcula. Se responde con nombre de archivo seguro,
MIME adecuado, `Cache-Control: no-store` y `nosniff`. Se rechazan resultados inexistentes,
ajenos, fallidos y desactualizados. Los históricos permanecen consultables en pantalla.

Se reutilizan `render_docx` y `render_pdf` de Statistics. Ambos reciben contexto opcional
compatible con sus llamadas anteriores: proyecto, paquete, plan, dataset, técnica,
justificación y aprobación, además de métricas, supuestos, advertencias e interpretación
almacenados. No se modificaron fórmulas, contratos ni el motor.

Corrección acotada del PDF: elimina el recorte de 48 líneas, envuelve texto y tokens
largos, pagina y escribe offsets/xref exactos. WinAnsi/CP1252 conserva español y los
literales `()`, `\\`, `&`, `<` sin convertirlos a HTML. Los caracteres fuera de WinAnsi
se sustituyen por `?` y se añade un aviso; DOCX conserva Unicode. El PDF sigue siendo
textual, sin gráficos, fórmulas enriquecidas ni tipografías embebidas.

## Estados y límites funcionales

Se conservan los estados de documentos vacíos/sin texto, IA no configurada y revisión
pendiente; datasets inexistentes/con problemas de calidad; paquete incompleto u obsoleto;
plan con aclaraciones, propuesto o aprobado; análisis completado/fallido e histórico
obsoleto. El origen de datasets originales se declara en el paso Dataset y los derivados
lo heredan al crearse. Si se creó un derivado antes de declarar el origen, vuelve a
prepararlo desde el original declarado; no se atribuye procedencia retroactivamente.

Solo descriptivos y Pearson están conectados al recorrido de proyectos. El catálogo y
las técnicas restantes de Statistics se conservan; sus adaptadores y visualizaciones
en este panel siguen pendientes. No se supone normalidad, linealidad ni ausencia de
atípicos por tener un coeficiente r. No se incorpora autenticación, Supabase, despliegue,
nuevas técnicas ni nuevas llamadas a proveedores externos.

## Verificación realizada

La regresión de esta sesión usa Python 3.12 del entorno `.venv` instalado y Node 24 con
los lockfiles existentes. El sandbox Windows bloqueaba los sockets internos de asyncio
y algunos temporales: las pruebas FastAPI se ejecutaron fuera del sandbox con aprobación.
No se alteró el código para eludir esa restricción. `uv run` también encontró una caché
no escribible; se usaron directamente los ejecutables del entorno equivalente instalado.

- Backend: **235/235 pruebas correctas** en la pasada final (53,86 segundos).
  Incluye los casos nuevos de aplicación e informes. Sin llamadas a Cloudflare.
- Frontend: **64/64 pruebas correctas** en 17 archivos (12,36 segundos).
- Ruff check y format, contratos JSON Schema, compileall, ESLint, Prettier, TypeScript:
  correctos tras las últimas correcciones.
- Build principal y Research independiente correctos. El principal incluye Statistics.
  El build independiente escribe en `dist/research-independent` para conservar la
  entrada principal `dist/research-demo/index.html` al ejecutar ambos builds seguidos.
- Pruebas E2E HTTP nuevas: creación y extracción DOCX reales, revisión manual confirmada,
  CSV, EDA original/derivado, preparación, activación, paquete, descriptivos y Pearson,
  aprobación, resultado, reinicio y exportaciones. Métricas comprobadas numéricamente.
- Descargas verificadas con `Document(BytesIO(...))` y `PdfReader(..., strict=True)`,
  buscando IDs, técnica, métricas y advertencias reales. El motor se hace fallar si se
  invoca durante la descarga, para demostrar que exportar no recalcula.
- Se comprueban referencias ajenas/inexistentes, formato inválido, POST con resultados
  arbitrarios, fallo, obsolescencia, CORS local y rechazo de clientes/hosts externos.
- Pruebas anteriores cubren aclaraciones, errores numéricos, fuentes cambiadas,
  compatibilidad sin aprobación automática y ejecución concurrente idempotente.
- Informes largos: más de 100 líneas, español, caracteres PDF literales y tokens largos.
  PDF real y versión larga de tres páginas renderizados con Poppler e inspeccionados:
  sin recortes ni superposición. Son material temporal de QA en `.cache`, no evidencias
  ni capturas para Notion.
- DOCX válido y reabierto con contenido completo. El renderizador empaquetado no pudo
  ejecutarse porque falta LibreOffice (`soffice.exe`); revisión visual DOCX pendiente.

### Navegador

Prueba real en navegador integrado sobre `http://localhost:5173/`: listado y creación
de proyecto ficticio, apertura de detalle, carga de DOCX, extracción de 357 caracteres,
IA sin configurar y creación/edición/guardado del borrador metodológico con dos variables.
Al intentar confirmar la revisión, la autorización del navegador para ese origen fue
rechazada. Se detuvo la automatización sin intentar otra vía para esa acción.

Por tanto, **no se acredita navegación manual completa hasta exportar ni recarga con
resultados desde navegador**. El recorrido completo está comprobado mediante HTTP,
almacenamiento, motor real y pruebas de componentes. Falta repetirlo en navegador con
acceso autorizado y revisar visualmente los DOCX en Word/LibreOffice. No se generaron
capturas ni documentación de evidencias para Notion. CI no sustituye esa prueba pendiente.

## Cambios principales

Entrada y estilos de aplicación, navegación de `ResearchProjects`, procedencia en
`ProjectDatasets`, actualización e histórico en `ProjectPackage`/`ProjectAnalysis`,
cliente de descargas, wrapper de compatibilidad Statistics; rutas/servicio de informes,
PDF paginado y composición local/CORS; scripts, pruebas, build/CI y documentación.
Los seis contratos v1.0.0 y `backend/app/main.py` permanecen sin cambios.

## Git y CI

Rama publicada: `feat/application-integration`, base `28816d0`. Commits de implementación:
`385dc50` (API/informes) y `6abad5a` (aplicación). Árbol limpio tras esos commits.
El intento de crear un PR borrador hacia `develop` mediante el conector GitHub devolvió
`403 Resource not accessible by integration`. No se intentó eludir la restricción.
Título y descripción quedan en [PR_APPLICATION_INTEGRATION.md](PR_APPLICATION_INTEGRATION.md).
No se fusionó ninguna rama. La verificación remota final se consigna en el informe
entregado. La consulta inicial por el conector devolvió
cero ejecuciones de PR para el commit de cierre de la sesión anterior; eso no se
interpreta como CI aprobada.

### Inventario de archivos de la sesión

```text
.github/workflows/ci.yml
README.md
backend/.env.example
backend/app/modules/research/dev_app.py
backend/app/modules/statistics/reports.py
backend/app/orchestration/analysis_routes.py
backend/app/orchestration/analysis_service.py
backend/scripts/create_demo_inputs.py
backend/tests/research/test_application_integration.py
backend/tests/test_reports.py
frontend/.env.example
frontend/package.json
frontend/src/app/App.tsx
frontend/src/app/App.test.tsx
frontend/src/app/styles.css
frontend/src/features/research/analysis/ProjectAnalysis.tsx
frontend/src/features/research/analysis/ProjectAnalysis.test.tsx
frontend/src/features/research/analysis/api.ts
frontend/src/features/research/analysis/api.test.ts
frontend/src/features/research/datasets/ProjectDatasets.tsx
frontend/src/features/research/datasets/ProjectDatasets.test.tsx
frontend/src/features/research/packages/ProjectPackage.tsx
frontend/src/features/research/packages/ProjectPackage.test.tsx
frontend/src/features/research/projects/ResearchProjects.tsx
frontend/src/features/research/projects/ResearchProjects.test.tsx
frontend/src/features/research/vite.demo.config.ts
frontend/src/features/statistics/ResearchStatisticsPanel.tsx
frontend/src/features/statistics/ResearchStatisticsPanel.test.tsx
frontend/vite.config.ts
docs/APPLICATION_INTEGRATION.md
docs/PR_APPLICATION_INTEGRATION.md
```
