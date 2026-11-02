# Research → Statistics: integración real de desarrollo

Sesión 13. Base: `develop@578ae277968fa99e4a6447300809a68d8c94a766`, con PR #11,
#12 y #13 fusionados. Antes de publicar se incorporó también `develop@f776dcd`
(PR #14 del compañero). Rama: `feat/research-statistics-e2e`. Los seis contratos
v1.0.0, el planificador, las fórmulas y los archivos de Statistics permanecen intactos.

Cierre de integración: se incorporó mediante merge normal `develop@33ec482`
(PR #15). Se resolvieron los conflictos de `ProjectPackage.tsx` y su prueba
conservando el aviso de paquete preparado del compañero y un único panel visible,
`ProjectAnalysis`, con planificación, aprobación independiente y ejecución.
`ResearchStatisticsPanel` y el módulo Statistics no se modificaron. Las pruebas
del paquete comprueban que no se monte el segundo panel ni se use su ruta anterior;
las pruebas backend mantienen el rechazo del atajo `approve=true`.

## Flujo y responsabilidades

1. Research crea el proyecto, almacena un documento y confirma una revisión
   metodológica manual. No hace falta llamar a Cloudflare.
2. El estudiante sube y activa un CSV/XLSX sintético, declara su origen y confirma
   diseño, observaciones, roles, escalas y vinculaciones de columnas e hipótesis.
3. `PackageService` valida las fuentes y construye el `ResearchPackage` vigente.
4. `ResearchAnalysisService` obtiene ese paquete mediante
   `ResearchStatisticsBridge.get_package` y llama al planificador del Integrante 2
   con una hipótesis existente. Verifica los IDs devueltos y asigna un UUID nuevo.
5. La demo muestra técnica, justificación, supuestos y preguntas. **Aprobar análisis**
   envía una confirmación independiente de esa propuesta concreta.
6. **Ejecutar análisis** revalida fuentes y llama al motor real con datos autorizados.
7. Guarda un `AnalysisResult` validado por Pydantic y muestra métricas, comprobaciones,
   advertencias y fallos. La recarga recupera el resultado sin volver a calcular.

El recorrido está en el detalle de la demo Research existente. `App.tsx` sigue
siendo la base técnica, y la demo Statistics conserva su funcionamiento independiente.

| Pieza | Responsabilidad |
| --- | --- |
| `orchestration/research_statistics.py` | Paquete vigente, pertenencia al proyecto y lectura autorizada de datos. |
| `orchestration/analysis_service.py` | Composición de planificación, aprobación, vigencia y ejecución. |
| `orchestration/analysis_inputs.py` | Columnas → `AnalysisInput` solo para Pearson; sin fórmulas. |
| `orchestration/analysis_repository.py` | SQLite local, historial por proyecto y ejecución serializada. |
| `orchestration/analysis_models.py` | Metadatos de integración alrededor de los contratos existentes. |
| `orchestration/analysis_routes.py` | API de desarrollo en loopback, solo datos sintéticos. |
| `statistics/research_bridge.BytesDatasetReader` | Lectura acotada de bytes y validación contra `DatasetReference`. |
| `statistics/engine.DeterministicStatisticalEngine` | Cálculos y comprobaciones existentes de Statistics. |

```python
reader = BytesDatasetReader(
    lambda reference: bridge.read_dataset(project_id, package, reference)
)
engine = DeterministicStatisticalEngine(
    reader, {package.dataset.id: package.dataset}, inputs
)
result = engine.execute(approved_plan)
```

Se reutiliza `build_engine_from_research_bridge` del PR #14 para descriptivos.
Pearson construye el mismo motor con su `AnalysisInput`, porque ese helper no
recibe entradas seleccionadas. No se utiliza directamente
`build_engine(DatasetService, ...)`: ese helper no llama al puente. La composición
exige referencia opaca válida, proyecto, actividad,
formato, columnas, filas, tamaño y vigencia antes y después de leer. Statistics
nunca recibe rutas privadas. Para la huella del documento se inyecta el puerto
público `DocumentRepository.read(project_id, document_id)`; su contenido no se
envía a Statistics. Ningún endpoint nuevo publica bytes.

## Planificación y aprobación

Estados del contrato: `needs_clarification`, `proposed`, `approved`. El cliente no
puede enviar una técnica, función, vectores ni un plan propio. El planificador decide
la técnica; la integración conserva su recomendación y justificación.

Además de las escalas `interval`/`ratio` exigidas por el planificador para Pearson,
el adaptador requiere diseño conocido, observaciones independientes declaradas,
roles conocidos y dos variables vinculadas a columnas distintas, una por variable.
Si faltan esas declaraciones, conserva la técnica sugerida, marca
`needs_clarification` y añade preguntas. No inventa metadatos metodológicos.
Las advertencias del paquete también permanecen visibles en la demo.

La aprobación requiere `confirm: true` y el `proposal_token` devuelto por el
servidor. La huella incluye propuesta concreta (sin su estado mutable), paquete y
versión de fuentes; no es autenticación. Las propuestas nuevas no reutilizan
aprobaciones anteriores. Una aprobación repetida conserva su fecha original y
no ejecuta nada. Se rechazan aclaraciones, obsolescencia y adaptadores pendientes.
Aprobar no declara que los supuestos hayan sido comprobados satisfactoriamente.

## Técnicas y cálculos comprobados

**Resumen descriptivo:** el motor existente resume todas las columnas del dataset
autorizado, no solo las variables de la hipótesis. Se conserva ese comportamiento.

CSV de referencia, o las mismas celdas guardadas como XLSX:

```csv
horas_estudio,rendimiento
1,2
2,4
3,6
4,8
```

| Métrica calculada | Esperado |
| --- | --- |
| `horas_estudio.mean`, `.median` | 2.5 |
| `horas_estudio.sample_variance` | 5/3 |
| `rendimiento.mean` | 5 |
| `rendimiento.sample_variance` | 20/3 |
| Pearson `n`, `r` | 4, 1 |

El caso derivado ejecuta la preparación real para eliminar `rendimiento`, activa
el CSV resultante, actualiza vinculaciones, reconstruye el paquete y verifica media 2.5.

**Pearson:** resuelve las columnas mediante los IDs de variables de la hipótesis.
Conserva orden de filas y celdas faltantes en `AnalysisInput.left/right`. El motor
selecciona pares completos y rechaza valores incompatibles/no finitos, columnas
constantes o menos de tres pares válidos. No se copian vectores en código productivo.

Otro CSV contiene `(1,1), (2,3), (vacío,999), (999,vacío), (3,2), (4,5)`.
Los cuatro pares completos dan `r = 5.5 / sqrt(43.75) ≈ 0.8315218406202999`.
Se informa la exclusión de dos filas y se conservan los diagnósticos del motor.
No se añaden p-valores ni afirmaciones de significancia. Con cuatro valores,
normalidad queda `not_checked`: el diagnóstico requiere al menos ocho.
Linealidad y valores atípicos requieren revisión antes de interpretar.

Las demás técnicas están implementadas en Statistics pero **no conectadas** desde
Research. Se muestra la técnica original y se bloquean aprobación y ejecución.
Los adaptadores pendientes corresponden a integración coordinada con el Integrante 2.
Tampoco se ha conectado la exportación de `statistics.reports` a la demo.

## API

Prefijo: `/api/research/projects/{project_id}/analysis`.

| Método y ruta | Entrada / respuesta |
| --- | --- |
| `POST /plan` | `{package_id, hypothesis_id}` → 201, registro y plan. |
| `GET /plans` | Registros del proyecto con aprobación y resultado; revalida vigencia. |
| `POST /plans/{plan_id}/approve` | `{confirm: true, proposal_token}` → registro aprobado. |
| `POST /plans/{plan_id}/execute` | Sin parámetros de técnica/vectores → `AnalysisResult`. |
| `GET /results` | Registros con resultado, también históricos señalados como obsoletos. |

Los registros públicos incluyen IDs, versión de fuentes, token, plan, fechas,
limitación, invalidación y resultado. No incluyen el paquete privado ni bytes.
El frontend recupera resultados mediante `GET /plans`, evitando otra solicitud redundante.

Errores: 404 para proyecto/hipótesis/plan inexistente o ajeno; 409 para paquete
obsoleto, referencias incompatibles, falta de aprobación o adaptador pendiente;
422 para entradas inválidas; 403 para acceso remoto o datos no sintéticos; 503 para
SQLite no disponible. Un fallo de cálculo devuelve 200 con
`AnalysisResult.status = failed`, métricas vacías y advertencias. Las excepciones
inesperadas del motor se convierten en fallos controlados sin detalle interno en HTTP.

Compatibilidad con PR #14: `POST /statistics/plan` conserva la respuesta
`AnalysisPlan`, pero registra la propuesta mediante el mismo servicio. Para
`POST /statistics/analysis` ahora se exige `plan_id` junto a paquete e hipótesis,
y aprobación previa en `/analysis/plans/{plan_id}/approve`. `approve=true` se
acepta como campo heredado, pero **no concede aprobación**. Sin ID/aprobación
devuelve 409 con instrucciones; no vuelve a proponer ni aprueba en la ejecución.
Ambas rutas aplican loopback y las restricciones sintéticas. Se conservaron el
helper, algoritmos y panel Statistics del compañero. Su panel anterior no se
monta en Research: su protocolo de ejecución queda pendiente de migración si
se reutiliza por separado. La demo integrada usa `ProjectAnalysis`.

## Persistencia, vigencia y reintentos

Tabla `research_analyses` en el `research_db_path` existente. Guarda proyecto,
paquete privado, plan, huella de propuesta, versión de fuentes, creación,
aprobación, invalidación y resultado. La versión combina configuración (incluidas
versiones y huellas de revisión/dataset) con bytes del documento metodológico.
El puente vuelve a comprobar el dataset. Se revalida antes y después de
aprobar/ejecutar y antes de devolver resultados cacheados.

Un cambio detectado invalida permanentemente el plan, elimina su aprobación activa
y exige otra propuesta. Conserva los resultados históricos sin permitir reejecutarlos.
El historial completo sigue accesible en la API aunque el paquete necesite
reconstruirse; la sección de análisis de la demo se monta junto a un paquete vigente.

`BEGIN IMMEDIATE` mantiene una transacción durante el cálculo. Los reintentos
simultáneos calculan una vez; el segundo devuelve el mismo resultado. También se
persisten fallos. Un cierre del proceso revierte la transacción, sin reservas colgadas.
Límites: bloqueo de escritura compartido, espera de cinco segundos, coste de lectura
y hash; sin cola ni garantías distribuidas. Los archivos no son transaccionales.
No hay auditoría de cambios intermedios de actividad restaurados antes de validar:
se comprueban el estado observable y las versiones de Research. Borrar un proyecto
impide consultar su historial, pero esta tabla no implementa purga física.

## Reproducir la demo

Desde `backend`, PowerShell:

```powershell
$env:CORS_ORIGINS = '["http://127.0.0.1:5174"]'
uv sync --locked
uv run uvicorn app.modules.research.dev_app:app --host 127.0.0.1 --port 8001
```

Desde `frontend`, otra terminal:

```powershell
npm ci
$env:VITE_RESEARCH_API_BASE_URL = 'http://127.0.0.1:8001'
npx vite --config src/features/research/vite.demo.config.ts --host 127.0.0.1
```

Abrir `http://127.0.0.1:5174/research-demo/index.html`. Crear proyecto ficticio,
adjuntar documento ficticio, extraer texto y crear revisión manual. Completar
título, objetivo, diseño, hipótesis y variables; guardar y confirmar. Subir el CSV
anterior y activarlo. En **Preparar investigación para análisis**, seleccionar
documento/dataset y origen sintético; confirmar diseño `observational`, observaciones
`independent`, roles y escalas `ratio`; vincular cada variable a su columna y la
hipótesis a ambas variables y al objetivo revisado. Elegir `descriptive` o
`association`, guardar vinculaciones, validar y generar paquete. Pulsar **Proponer
análisis**, revisar, **Aprobar análisis**, **Ejecutar análisis**. Recargar y reabrir
el proyecto para comprobar persistencia.

## Evidencia de la sesión

- Backend completo: **229 pruebas aprobadas**, incluidas **34 nuevas** en
  `tests/research/test_analysis_e2e.py`. Los casos reales usan HTTP de Research,
  SQLite, documentos/datasets almacenados, planificador y motor existentes.
  Cubren CSV/XLSX, derivado, pertenencia, fuentes obsoletas, documento modificado,
  aclaraciones, aprobación, faltantes, errores numéricos, reintento y recarga.
  Pydantic valida planes/resultados; la regresión valida los seis esquemas compartidos.
  También se adaptan las dos pruebas runtime del PR #14 para la aprobación
  independiente y se añade una prueba contra el atajo `approve=true`, aclaraciones
  y referencias incompatibles en sus rutas de compatibilidad.
- Unidad: rechazo del adaptador frente a una tabla sin columna vinculada; esa
  llamada aislada no sustituye las pruebas del recorrido completo.
- Mocks/instrumentación: inyección de excepción inesperada del motor y contador
  alrededor del motor real para demostrar deduplicación. No sustituyen cálculos reales.
- Frontend: **63 pruebas aprobadas** en 17 archivos; 8 nuevas de API/componente,
  más 3 de paquete actualizadas. Sus respuestas HTTP son simuladas. Comprueban
  acciones separadas, métricas, advertencias, recuperación visual, aclaraciones,
  obsolescencia, límites y errores; no son pruebas de backend.
- Ruff check/format check, compilación Python, ESLint, Prettier, TypeScript,
  build principal (incluye Statistics) y build Research: aprobados.
- Navegador integrado, **2 de noviembre de 2026**: fuentes sintéticas aisladas
  preparadas mediante los endpoints Research usados por las pruebas. Se pulsaron
  los botones reales de propuesta, aprobación y ejecución Pearson: `n=4`, `r=1`,
  normalidad `not_checked`, advertencia de ausencia de p-valor. Recargar y reabrir
  recuperó aprobación/resultado. Consola sin errores ni advertencias. Backend:
  POST plan 201, approve 200, execute 200, GET plans 200. Se usaron puertos
  18013/15174 porque 5174 estaba ocupado. No se repitió manualmente la preparación
  metodológica completa en navegador; sí mediante pruebas HTTP reales.
  Tras incorporar PR #14 se verificó nuevamente Pearson persistido, se cambió
  el tipo a descriptivo mediante la interfaz, se observó la obsolescencia del
  paquete anterior y se generó/aprobó/ejecutó otra propuesta. La demo mostró
  media 2.5 y varianza 1.6666666666666667; el resultado Pearson anterior quedó
  etiquetado como histórico y perdió su aprobación activa.

El sandbox Windows bloqueó el socket interno de asyncio de `TestClient`; la
regresión se ejecutó con autorización fuera del sandbox. `uv` encontró un bloqueo
de caché; se usó Python 3.12 del entorno `.venv` existente. Cachés y capturas están
en `.cache`, excluidas de Git.

## Seguridad y pendientes

La demo no autentica personas. Las rutas nuevas verifican peer loopback y Host
local y solo admiten datasets declarados sintéticos. Esto no sustituye autorización
por propietario, CSRF, auditoría ni controles de producción. No publicar esta demo
ni cargar datos reales; los endpoints previos conservan sus límites de desarrollo.
`synthetic` es una declaración humana, no un detector de datos personales.
No hubo llamadas a Cloudflare/Supabase ni despliegue público.

Pendiente de coordinación: adaptadores del resto del catálogo, comprobación completa
de supuestos, inferencia/p-valores según contratos y motor disponibles, informes
exportables y persistencia/autenticación de producción. No se demostró un defecto
bloqueante que requiriera modificar algoritmos del Integrante 2.

## Archivos de esta integración respecto de develop con PR #14

Nuevos:

- `backend/app/orchestration/analysis_inputs.py`
- `backend/app/orchestration/analysis_models.py`
- `backend/app/orchestration/analysis_repository.py`
- `backend/app/orchestration/analysis_routes.py`
- `backend/app/orchestration/analysis_service.py`
- `backend/tests/research/test_analysis_e2e.py`
- `frontend/src/features/research/analysis/api.ts`
- `frontend/src/features/research/analysis/api.test.ts`
- `frontend/src/features/research/analysis/ProjectAnalysis.tsx`
- `frontend/src/features/research/analysis/ProjectAnalysis.test.tsx`
- `docs/RESEARCH_STATISTICS_E2E.md`

Modificados:

- `backend/app/modules/research/dev_app.py`
- `backend/app/orchestration/statistics_routes.py`
- `backend/tests/research/test_statistics_runtime.py`
- `frontend/src/features/research/packages/ProjectPackage.tsx`
- `frontend/src/features/research/packages/ProjectPackage.test.tsx`
- `frontend/src/features/research/projects/ResearchProjects.tsx`
- `frontend/src/features/research/projects/projects.css`
- `docs/RESEARCH_PACKAGE.md`
- `docs/RESEARCH_STATISTICS_INTEGRATION.md`
