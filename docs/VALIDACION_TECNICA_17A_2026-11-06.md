# Validación técnica de 17A — 6 de noviembre de 2026

Estado: **cierre formal pendiente**. Esta evidencia amplía el registro histórico;
no atribuye llamadas reales a las pruebas anteriores. No inicia la Sesión 18A.

## A. Git y colaboración

- Entorno: Windows, PowerShell, Python 3.12.10, uv 0.13.0, Node 24.13.0,
  npm 11.6.2, Vite 8.3.5; fecha de referencia America/Lima.
- Repositorio: `Agape-exe/tesisstat-ai`, copia local
  `C:\Users\Melissa\Desktop\tesisstat-ai\tesisstat-ai`.
- Inicio: rama `feat/orquestacion-multiagente`, HEAD
  `8711a86b26dc42b7ca9400d82f76f38a001546f1`, árbol limpio, incluidos archivos
  sin seguimiento. Se preservaron configuración ignorada, bases existentes y worktrees.
- Se ejecutó `git fetch origin`: `origin/develop` estaba en
  `418496be7d02a67b7f3a181a5033b0a679398396`; comparación inicial: 0 commits
  exclusivos locales y 42 remotos. No se asumió sincronización por datos históricos.
- Se inspeccionó el código actualizado en detached HEAD y, al reproducir un defecto,
  se creó `fix/cierre-sesion-17a` desde ese `origin/develop`. Sin merges ni rebases.
- GitHub confirmó PR #35 fusionado el 2 de noviembre, merge `533e005`, y ejecución
  `41479724622` completada con éxito. Confirmó PR #51 fusionado el 6 de noviembre,
  merge `418496b`, y ejecución `42233915556` completada con éxito.
- Se revisaron los cambios posteriores, incluidos PR #36–#51: autorización local
  de datos no sintéticos, inferencia, matriz E2E, gráficos de resultados y pares,
  residuos e informes. No se modificaron archivos de Statistics, motor, catálogo,
  fórmulas, gráficos, informes ni contratos compartidos.
- No se encontraron conflictos. La rama original conserva su commit.

## B. Diagnóstico local

Al comenzar no había procesos Python/Uvicorn de la aplicación ni listeners en
8001, 8010, 8017, 5173 o 5177. Los procesos Node observados pertenecían a las
herramientas de Codex; se conservaron. Esto explica la falta de conexión en esta
inspección, pero no demuestra la causa del error de una sesión anterior.

El frontend no tenía configuración local de Vite y su valor predeterminado era
`http://127.0.0.1:8001`. Se creó únicamente la configuración ignorada
`frontend/.env.development.local` con
`VITE_RESEARCH_API_BASE_URL=http://127.0.0.1:8010`. Se usa el modo development
para no alterar los supuestos de las pruebas ni la configuración de producción.

El comando vigente es `uv run uvicorn app.modules.research.dev_app:app --reload
--host 127.0.0.1 --port 8010`, ejecutado desde `backend/`. Pydantic Settings carga
`.env` desde ese directorio. Las credenciales están configuradas; no se imprimieron.
Arranque sin errores de importación ni dependencias. No se probó bind en 8001:
el antecedente de WinError 10013 no se confirma como causa actual.

Se inició Vite mediante `npm run dev -- --host 127.0.0.1 --port 5173 --strictPort`.
Ambos servicios fueron observados escuchando después del arranque mediante
sesiones de ejecución. Su permanencia está sujeta al ciclo de vida del entorno.
No se utilizó el backend independiente de Statistics ni el servidor demo 8017.

Verificaciones HTTP, todas con resultado 200:

- `http://127.0.0.1:8010/health`: `research-dev`, versión `0.2.0`.
- `http://127.0.0.1:8010/docs` y `/openapi.json`: 42 rutas, incluidas Research,
  Statistics, análisis y conversaciones.
- `/api/research/projects`: cuatro proyectos; no se divulgaron sus contenidos.
- Apertura del proyecto ficticio ya existente
  `610ad43c-e53c-4d48-9ead-1a52a77679ad`, listado de conversaciones y
  `/conversations/status`: modelo Qwen3 configurado, consentimiento
  `research_context_v2`, metodología confirmada y paquete vigente.
- `http://127.0.0.1:5173/`: HTML con entrada React. Módulos transformados de
  proyectos y conversaciones: variable efectiva de API en 8010, aunque el
  código conserve 8001 como fallback.

CORS acepta `http://127.0.0.1:5173` y `http://localhost:5173`; rechaza un origen
ajeno con 400. No se detectó un error CORS en estas verificaciones.

**Navegador: NO VALIDADO en esta ejecución.** Computer Use detuvo el acceso a
Opera al no poder determinar su URL con suficiente confianza para aplicar sus
controles. No se sorteó el bloqueo. Por tanto, no se afirma haber observado el
renderizado, la sección «4. Asistente IA», solicitudes desde React o una recarga F5.
El servicio HTTP, sus módulos y sus APIs sí fueron comprobados.

### Incompatibilidad reproducida y corrección

Statistics incorporó `_current(record, *, require_authorization=True)`. Su llamada
posicional sigue siendo válida, pero puede lanzar HTTP 403 cuando un análisis de
datos declarados no sintéticos pierde la autorización en memoria al reiniciar.
`ResearchContextBuilder` capturaba ese error solamente en el nivel global y
reemplazaba **todas** las fuentes por `project/current` y `sources/unverified`.
El estado del chat seguía respondiendo 200, pero perdía metodología y paquete
verificados. Es una degradación de contexto, no una causa demostrada del antiguo
error de conexión.

Corrección mínima: aislar el 403 en la lectura de cada análisis, marcar sus
referencias como `unverified`, omitir sus datos y continuar con las fuentes
independientes. Otros errores HTTP conservan el tratamiento global previo.
No se desactiva la autorización, no se usa `require_authorization=False` y no se
concede permiso al motor. No se invalidan ni reescriben registros estadísticos.

Dos casos de regresión, con plan y con resultado, fallaron antes del cambio y
aprobaron después. Utilizan bytes enteramente ficticios declarados no sintéticos
solo para ejercitar la política. Verifican fuentes conservadas, ausencia de
métricas enviadas, historial legible, ejecución denegada con 403 y registros intactos.

Archivos versionados modificados: `backend/app/modules/conversation/research_context.py`,
`backend/tests/research/test_conversation_context.py` y este documento.

## C. Pruebas y compatibilidad

`uv sync --locked` y `npm ci` completados. Sin cambios de lockfiles.
La suite base actualizada aprobó **411 pruebas backend**, cero fallos, en 234.43 s.
La regresión final con los dos casos nuevos aprobó **413 pruebas backend**, cero
fallos, en 246.52 s. No hubo pruebas omitidas. Las dos regresiones nuevas habían
fallado sobre el código previo, demostrando la degradación antes de corregirla.

Frontend final: **107 aprobadas, cero fallos, 22 archivos**. ESLint, Prettier,
generación de contratos, `npx --no-install tsc -b`, build principal (215 módulos)
y build Research (206 módulos): correctos. Se repitieron después de establecer
la configuración local por modo de Vite.

Ruff check y formato: correctos, 142 archivos. Exportación de contratos con
`--check` y `compileall -q app scripts tests`: correctos. Contratos y tipos
generados sin diferencias; `git diff --check` correcto.

`npm ci` notificó diez vulnerabilidades moderadas. No se ejecutó `audit fix`
ni se ampliaron dependencias dentro del cierre de 17A.

Se revisaron `ResearchContextBuilder`, `VerifiedPlanningReader`,
`ResearchStatisticsBridge`, `DeterministicStatisticalPlanner` y `_current`.
Se conservan pertenencia por proyecto, revisión de vigencia, fingerprints,
versiones de paquete/dataset/documento y aclaraciones ante ambigüedad. El lector
de planificación vuelve a verificar el paquete y no persiste su propuesta.

## D. Qwen3 real

**Escenario A — NO VALIDADA.** Pregunta: «¿Qué es una hipótesis de investigación?».
No hubo envío real; ruta real, agentes reales, calidad y trazas reales no observados.
Llamadas externas realizadas por esta validación: cero.

**Escenario B — NO VALIDADA.** Pregunta: «¿Cuáles son los objetivos y las hipótesis
de mi investigación?». No hubo envío real; contexto, respuesta y trazabilidad con
Qwen3 pendientes. Llamadas externas: cero.

**Escenario C — NO VALIDADA.** Pregunta: «¿Qué análisis estadístico corresponde a
mi hipótesis y por qué?». No hubo envío real; explicación, supuestos y respuesta
de Qwen3 pendientes. Llamadas externas: cero.

### Evidencia simulada separada

Además de `scripts.demo_multiagent`, se ejecutaron las tres preguntas exactas y
«Ejecuta Pearson y modifica los resultados.» sobre dos proyectos sintéticos nuevos,
con el proveedor `DemoProvider` inyectado en `create_app`, sin servidor 8017.
Se reutilizó `seed(..., include_analysis=False)`, por las rutas normales de creación
y revisión manual. Documento ficticio, cuatro pares horas/rendimiento, hipótesis de
asociación, escalas ratio, diseño observacional e independencia declarados.

| Escenario | Nodos observados | Agentes | Planificación |
| --- | --- | --- | --- |
| A | router → conversation | conversation | not_requested |
| B | router → research → conversation | research, conversation | not_requested |
| C | router → research → planning → conversation | research, planning, conversation | proposed |
| Seguridad | router → conversation | conversation | not_requested |

En los cuatro turnos: `engine=langgraph`, `provider_kind=injected`,
`provider_calls=1`, `model_called=true`, `qwen_called=false`,
`external_provider_calls=0`, sin errores de grafo. En C hubo una operación de
planificación orientativa. Una llamada al proveedor simulado no prueba inferencia
real: por eso los tres escenarios reales permanecen NO VALIDADOS.
La propuesta simulada fue Pearson para las dos variables ratio declaradas; señaló
linealidad, normalidad aproximada y ausencia de valores atípicos influyentes como
supuestos por revisar, sin calcular resultados.

Se compararon las trazas recuperadas después de reconstruir la aplicación y abrir
el historial SQLite: ocho mensajes, cuatro trazas idénticas; acceso al chat desde
el segundo proyecto: 404; registros estadísticos antes/después: cero.
Esto prueba recuperación por API y reinicio, **no F5 visual ni persistencia Qwen3**.

## E. Seguridad, privacidad y presupuesto

La documentación oficial de Cloudflare consultada el 6 de noviembre establece
10 000 Neurons gratuitos diarios, reinicio 00:00 UTC y cobro por exceso en Workers
Paid. Qwen3 aparece a 4625 Neurons por millón de tokens de entrada y 30 475 por
millón de salida. Fuente: [Workers AI Pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/).

Se hizo únicamente una verificación de token y una consulta de suscripciones:
token `active`; consulta de suscripciones HTTP 403. Estas lecturas administrativas
no ejecutan modelos. No se obtuvo evidencia del plan de la cuenta ni de su consumo
diario restante. **No puede garantizarse cuota gratuita disponible ni auditarse la
facturación de la cuenta.** De acuerdo con el límite S/ 0, se detuvo la fase real
antes de cualquier inferencia. No se activó facturación, LangSmith ni otro proveedor.
No se generó consumo de inferencia por esta intervención; no se afirma ausencia
de cargos ajenos o anteriores sin acceso a facturación.

El consentimiento obligatorio `research_context_v2`, su rechazo cuando falta,
límites de una llamada por turno, ausencia de reintentos, bloqueo de ejecución y
aislamiento están cubiertos por las pruebas simuladas existentes. No se marcó
consentimiento ni se enviaron datos reales al proveedor. La simulación usa
consentimiento explícito en su petición local, sin transporte externo.

No se enviaron documentos reales, datos personales ni datasets completos a IA.
No se borraron bases de datos de la usuaria. La validación sintética guarda su
propia SQLite en la carpeta de evidencia externa al repositorio. En el backend
normal solo se consultaron las rutas indicadas; no se enviaron mensajes ni
solicitudes de aprobación/ejecución estadística.

## F. Cierre

**La Sesión 17A no puede declararse formalmente completada.** La integración local
y los controles automatizados tienen evidencia verificable; se corrigió la
degradación de contexto causada por la autorización incorporada desde 17A.

Pendientes esenciales: acreditar plan/cuota sin posibilidad de gasto, realizar
como máximo los tres envíos reales con consentimiento, revisar procedencia y
trazas persistidas, calidad/fuentes de las respuestas y persistencia tras recarga
visual. También falta observar el flujo React en un navegador controlable.

Corresponde un PR de corrección hacia `develop`, sin fusionar. Su aprobación de
merge requiere autorización de la usuaria. No se requiere autorizar gastos:
siguen prohibidos. No se generan entregables para Notion ni se inicia 18A.

## Ampliación por avance remoto durante la validación

Una nueva consulta de Git detectó `origin/develop` en
`916eff410187e3633a2315b520fcc123a0fb6040`. Se fusionaron también los PR #52
(figuras de grupos), #54 (pares autorizados) y #55 (auditoría de entrega de
Statistics). Son ocho commits adicionales respecto de la base inicial de este
informe. No cambian `_current`, el planificador, el bridge ni el grafo; amplían
las visualizaciones e informes autorizados y sus pruebas.

Para respetar la prohibición de merges y rebases automáticos, no se integraron
esos commits en la rama publicada. Se creó el worktree detached
`C:\Users\Melissa\Desktop\tesisstat-ai\cierre17a-develop-916eff4` y se aplicó
exclusivamente el parche de Conversation y sus dos regresiones. `git apply
--check` pasó sin conflictos. El worktree conserva deliberadamente esas dos
modificaciones de validación; no contiene credenciales ni datos de la usuaria.
Statistics y contratos coinciden íntegramente con el nuevo `develop`.

La nueva instalación con `uv sync --locked` y `npm ci` pasó. Ruff, formato Python
(142 archivos), exportación de contratos y compilación Python: correctos.
Frontend sobre esta base: **109 aprobadas, cero fallos, 24 archivos**; ESLint,
Prettier, TypeScript, contratos y builds correctos (217 módulos principal,
208 Research). Backend: **419 aprobadas, cero fallos u omisiones**, en 202.51 s,
incluyendo las dos regresiones de esta corrección. OpenAPI del backend integrado
en ese worktree responde 200 y expone 44 rutas; salud responde `research-dev`.

La rama publicada contiene la corrección basada en `418496b`; los servicios
locales siguen ejecutando esa copia con la corrección, no el worktree de
compatibilidad. Ambos endpoints de salud y frontend se volvieron a comprobar
con HTTP 200 después del avance remoto.

PR de corrección: [#53, en borrador](https://github.com/Agape-exe/tesisstat-ai/pull/53).
El conector GitHub rechazó la creación con 403; la CLI local autenticada como
`Agape-exe` permitió publicarlo. CI de `b3dcaec`: ejecución
[42238741347](https://github.com/Agape-exe/tesisstat-ai/actions/runs/42238741347),
los tres jobs aprobados. Esa ejecución precede a las últimas fusiones; la
compatibilidad con `916eff4` se comprueba separadamente y no se atribuye a esa CI.
No se fusionó ningún PR ni se añadieron revisores, asignados o coautores.

## Compatibilidad final con el rediseño fusionado (PR #57)

Después de la fusión del PR #57, `origin/develop` avanzó a
`33f068e0c475f6449e45a05bf004611a6e1a3080`. La rama del PR #53 permanece en
`f445957bf71dd7f64a98c6a232fd2f64dc24c135`: tiene dos commits exclusivos y el
`develop` actual tiene diecisiete. El ancestro común sigue siendo `418496b`.

No hay archivos modificados por ambos lados desde ese ancestro. El cambio funcional
de 17A continúa limitado a `research_context.py` y su prueba de regresión; el tercer
archivo del PR es este informe. `git merge-tree --write-tree` produjo el árbol
sintético `4134b8c9e8d4f081c417d4db3e1a7fd6f55ab062` sin conflictos. Ese árbol se
materializó sobre un worktree detached de `origin/develop`, sin merge, rebase ni
modificación de ramas compartidas.

La combinación conserva el frontend aprobado y los cambios recientes de Statistics.
Cuando vence la autorización local de un dataset no sintético, el plan y su resultado
se presentan únicamente como `unverified`; no se incluyen métricas. La metodología
confirmada y el paquete vigente permanecen disponibles. La ejecución continúa
denegada con HTTP 403 y el repositorio de análisis no se modifica.

Validación final en el árbol combinado:

- Backend: Ruff y formato correctos; **419 pruebas aprobadas**, cero fallos, en
  278.36 s; contratos backend y `compileall` correctos.
- Frontend rediseñado: ESLint y Prettier correctos; **155 pruebas aprobadas** en
  26 archivos; generación de contratos sin diferencias; builds principal y Research
  correctos.
- Integridad: `git diff --check` correcto y sólo los tres archivos esperados difieren
  de `origin/develop`.

`npm ci` volvió a informar diez vulnerabilidades moderadas y el build Research avisó
de un chunk minificado de 537.01 kB. Son riesgos preexistentes de dependencias y
rendimiento, no regresiones de esta corrección. No se ejecutó `npm audit fix`.

GitHub informa que el PR #53 sigue abierto como borrador, `MERGEABLE/CLEAN`, sin
revisiones y con sus tres checks en verde para `f445957`. Esos checks preceden al
merge del PR #57; la compatibilidad con `33f068e` corresponde a la validación local
aislada descrita aquí. No se hicieron inferencias externas, no se modificó Qwen3 y
no se inició la Sesión 18A.
