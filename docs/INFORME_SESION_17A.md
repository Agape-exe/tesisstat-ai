# Informe de implementación — Sesión 17A

Fecha: 2 de noviembre de 2026 (America/Lima). Rama: `feat/orquestacion-multiagente`.
Base: `693cde2`, `origin/develop`, con Sesión 16A/PR #30 y cambios del compañero/PR #31.
Árbol inicial limpio; actualización por fast-forward. Se detectó además la rama remota
`feat/statistics-inference-quality`, sin incorporarla ni modificar su trabajo.

## 1. Resultado ejecutable

Se implementó un sistema de tres agentes coordinado por `StateGraph` de LangGraph 1.2.19,
compilado mediante `compile()` y ejecutado desde el chat existente. Son operaciones
diferenciadas de comprensión de investigación, planificación determinista y generación
conversacional. El grafo tiene un enrutador real y transiciones condicionales observables
con `CompiledStateGraph.stream()` en las pruebas de arquitectura.

| Solicitud | Nodos ejecutados |
| --- | --- |
| Definición general | router → conversation |
| Metodología, variables, datos o resultados | router → research → conversation |
| Planificación estadística | router → research → planning → conversation |
| Intención ambigua sin contexto | router → conversation, con aclaración |
| Ejecución/aprobación/modificación desde chat | router → conversation, con bloqueo |

No hay ciclos. El enrutador normaliza tildes/mayúsculas y usa reglas españolas explícitas.
Los seguimientos breves pueden conservar la ruta anterior desde trazas backend persistidas,
pero recuperan fuentes actuales. Identificadores escritos en el mensaje no conceden permisos.

## 2. Agentes e integraciones

**Research Understanding:** usa `ResearchContextBuilder` y las fuentes persistidas de
metodología confirmada, objetivos, hipótesis, variables/dimensiones/escalas, dataset,
EDA, preparación, paquete, planes y resultados. Distingue borradores, ausencias, vigencia
y resultados históricos. No extrae documentos ni vuelve a llamar al modelo.

**Statistical Planning:** usa un puerto estrecho `VerifiedPlanningReader`, el bridge
validado por proyecto, el planificador determinista existente y validaciones metodológicas
de `analysis_inputs`. Verifica paquete/dataset, revisión humana, hipótesis inequívoca y
huella de fuentes. Devuelve técnica/justificación/supuestos o preguntas pendientes.
La propuesta es orientativa en memoria, no persistida, no aprobada y no ejecutable desde
el chat. No se reimplementan fórmulas ni técnicas ni se llama al motor.

**Conversational:** conserva `CloudflareLanguageModel.chat()`, selección de hechos enteros,
historial reciente y límites. Prepara la única llamada al proveedor y valida su respuesta.
En producción local configurada sigue usando el Qwen3 existente; en pruebas/demo se inyecta
un proveedor simulado identificado expresamente.

`ConversationService` mantiene endpoints, proyecto, consentimiento ampliado, idempotencia,
concurrencia, errores, historial, paginación, borrado y separación por proyecto. El grafo
reemplaza la generación directa, sin duplicarla. SQLite sigue siendo la fuente de verdad;
no se crea un segundo historial ni un checkpointer independiente.

Se corrige una lectura con efectos secundarios: el contexto consulta el repositorio de
análisis y reutiliza su validador interno de solo lectura `_current(record)`, evitando las
invalidaciones persistidas de `ResearchAnalysisService.list()`. Se preservan verificaciones
de versión/token/procedencia y se calcula el estado histórico en memoria. Las pruebas
comprueban que los payloads estadísticos almacenados permanecen idénticos, incluso con
fuentes desactualizadas.

## 3. Costos, límites y seguridad

- Turno completado: **máximo una operación `chat()`**. Router, Research y Planning: cero
  llamadas al modelo. Repetición idempotente completada: cero llamadas nuevas.
- Configuración: cuatro pasos, una llamada al modelo, una operación de planificación,
  contexto de 10000 bytes, salida de 1024 tokens y deadline de 120 segundos por defecto.
- Se conservan además los límites Cloudflare, incluido su timeout de transporte.
- Deadline cooperativo: se detecta exceso antes/después de nodos y antes del proveedor;
  se descartan respuestas tardías. No interrumpe CPU-bound ni operaciones síncronas en curso.
- Cero servicios externos utilizados en pruebas/demo. No LangSmith contratado, búsqueda
  externa desde la aplicación, proveedor nuevo, reintento automático ni despliegue.
- LangGraph incorpora SDKs y `langsmith` transitivamente; el trazado se deshabilita
  explícitamente incluso cuando variables del entorno lo habilitan. No se agrega el
  paquete completo `langchain`.
- Proyecto/conversación y fuentes se validan en backend. No hay herramientas arbitrarias,
  código generado ejecutable, aprobaciones, escrituras de metodología/dataset/planes ni
  cálculos estadísticos desde el grafo.
- No se transmiten documentos completos ni filas. El texto libre sigue requiriendo datos
  ficticios y revisión humana; la redacción de identificadores no garantiza detectar toda
  información personal. La aplicación permanece local y sin autenticación multiusuario.

**Costo de servicios de esta sesión: S/ 0. Llamadas a Qwen3 real: 0.**

## 4. Traza y frontend

Se extiende `Message.context` sin perder referencias/versiones/huellas de la Sesión 16A.
`multiagent` registra versión `17a.1`, motor `langgraph`, intención, nodos y agentes
iniciados, planificación, referencias verificadas, pasos, operaciones, proveedor, intentos
de llamada y códigos de error. Distingue proveedor inyectado de Cloudflare; la demo tiene
`external_provider_calls=0` y `qwen_called=false`.

Las respuestas completadas persisten su traza en el asistente. Los fallos controlados la
guardan en el mensaje de usuario reservado, sin crear una respuesta confirmada. No se
registran prompts completos, credenciales o razonamiento privado en logs.

El chat muestra «Agentes utilizados» con los participantes de esa respuesta. Una respuesta
antigua sin traza no muestra agentes supuestos. Se mantiene el panel de fuentes y se evita
presentar una consulta general sin snapshot como desactualizada o como cambio de fuentes.

## 5. Archivos creados

- `backend/app/orchestration/multiagent/__init__.py`
- `backend/app/orchestration/multiagent/state.py`
- `backend/app/orchestration/multiagent/router.py`
- `backend/app/orchestration/multiagent/tools.py`
- `backend/app/orchestration/multiagent/graph.py`
- `backend/app/orchestration/agents/conversational/agent.py`
- `backend/app/orchestration/agents/research_understanding/agent.py`
- `backend/app/orchestration/agents/statistical_planner/agent.py`
- `backend/scripts/demo_multiagent.py`
- `backend/tests/research/test_multiagent.py`
- `docs/ORQUESTACION_MULTIAGENTE.md`
- `docs/INFORME_SESION_17A.md`

## 6. Archivos modificados

- `README.md`
- `backend/.env.example`
- `backend/pyproject.toml`
- `backend/uv.lock`
- `backend/app/modules/conversation/context.py`
- `backend/app/modules/conversation/ports.py`
- `backend/app/modules/conversation/research_context.py`
- `backend/app/modules/conversation/service.py`
- `backend/app/modules/conversation/sqlite_repository.py`
- Los tres `README.md` de `backend/app/orchestration/agents/`.
- `backend/scripts/demo_context_chat.py`: permite reutilizar el sembrado sin crear/ejecutar análisis.
- `backend/tests/research/test_conversation_context.py`: adaptación del puerto de inyección de
  corrupción al repositorio de solo lectura, conservando todas las aserciones.
- `frontend/src/features/conversation/api.ts`
- `frontend/src/features/conversation/ConversationChat.tsx`
- `frontend/src/features/conversation/ConversationChat.test.tsx`
- `frontend/src/features/conversation/conversation.css`

## 7. Verificación local

| Comprobación | Resultado |
| --- | --- |
| Pytest completo | **385 aprobadas**, 0 fallidas |
| Pruebas nuevas multiagente | **47 casos** incluidos en la regresión |
| Vitest | **99 aprobadas**, 19 archivos, 0 fallidas |
| Ruff check | Correcto |
| Ruff format --check | **139 archivos** con formato correcto |
| `uv sync --locked` | Correcto, LangGraph 1.2.19 bloqueado |
| Importación de la aplicación | Correcta |
| Exportación/check contratos | Correcto; contratos sin diferencias |
| Compilación Python | Correcta |
| ESLint y Prettier | Correctos |
| TypeScript | Correcto, `tsc -b` |
| Generación contratos frontend | Correcta, sin cambios generados |
| Build principal | Correcto, **210 módulos** |
| Build Research independiente | Correcto, **201 módulos** |
| `git diff --check` | Correcto |

La cobertura incluye compilación/stream real del grafo, español con/sin tildes, rutas,
participación real, paquetes/metodología inexistentes o desactualizados, escalas desconocidas,
ambigüedad, condiciones pendientes, propuesta sin persistir, bloqueo, presupuestos,
deadline, respuesta tardía, errores/cuota/configuración, simulación sin telemetría y
ausencia de escrituras. Las suites anteriores siguen comprobando reinicio, historial,
concurrencia, idempotencia, consentimiento y separación por proyecto. No se borran ni
debilitan pruebas existentes.

## 8. Verificación de extremo a extremo

Se comprobó desde el navegador la cadena UI → API local → fuentes SQLite → grafo → UI:

1. Proyecto sintético abierto y navegación al Asistente IA.
2. Creación de conversación y bloqueo del formulario sin consentimiento.
3. Aceptación de consentimiento y envío de las cuatro preguntas A–D.
4. Rutas visibles de uno, dos y tres agentes; respuesta de ejecución bloqueada.
5. Propuesta Pearson orientativa con condiciones, sin aprobación/ejecución.
6. Recarga de página: historial y agentes recuperados; consentimiento vuelve a solicitarse.
7. Consola del navegador sin errores ni advertencias y respuestas HTTP 200/201.

Se usó backend demo `127.0.0.1:8017` y frontend `127.0.0.1:5177`; el puerto 5176 estaba
ocupado y no se detuvo su proceso. Captura local de revisión en
`backend/.cache/demo17a-chat.jpg` (ignorada por Git, sin evidencia Notion).

## 9. Demostración manual reproducible

Desde `backend/`: `uv run python -m scripts.demo_multiagent` imprime los cuatro escenarios,
respuestas simuladas y trazas reales. No necesita credenciales. Para interfaz:

```powershell
# Terminal 1, backend/
uv run python -m scripts.demo_multiagent --serve
# Terminal 2, frontend/
$env:VITE_RESEARCH_API_BASE_URL='http://127.0.0.1:8017'
npm run dev -- --port 5177
```

Abrir `http://127.0.0.1:5177/`, elegir proyecto sintético 1, abrir Asistente IA, crear
conversación y aceptar consentimiento. Preguntar definición de hipótesis, objetivos e
hipótesis propias, análisis correspondiente y «Ejecuta Pearson y modifica los resultados».
Observar agentes, fuentes, aclaraciones y bloqueo. Recargar y cambiar al proyecto vacío
para comprobar aislamiento. No borrar la base de datos habitual.

## 10. Límites y clasificación de capacidades

**Ejecutables:** grafo local compilado, rutas condicionales, recuperación de fuentes,
planificación determinista orientativa, generación por el puerto actual, persistencia,
límites y trazabilidad.

**Comprobadas con proveedor simulado:** recorrido completo de chat/UI, cuatro escenarios,
historial/F5, errores, presupuestos y una llamada por turno. Research, LangGraph y el
planificador se ejecutan realmente; solo la respuesta del modelo está simulada.

**Pendientes de validación real:** calidad de las respuestas y latencia del recorrido 17A
con Qwen3 en Cloudflare y su cuota gratuita. La validación real anterior de 15A/16A no
sustituye la de este flujo nuevo. No se presenta la demo como inferencia de Qwen3.

**Sesiones posteriores:** mejora de paráfrasis del enrutador con ejemplos validados;
evaluar creación explícita de planes desde chat con aprobación humana. No se implementan
esas ampliaciones ni funciones estadísticas del compañero. El timeout no garantiza
cancelación forzosa; el lector depende del validador interno `_current` y debe revisarse
si cambia esa interfaz.

## 11. Publicación y colaboración

Rama obligatoria `feat/orquestacion-multiagente`, commits en español y autoría Git existente.
Destino del PR: `develop`; no se modifica `main`, no se fuerza push, no se fusiona ni se
añade Codex como colaborador, revisor, asignado o coautor.

Los identificadores de commits, enlace del PR y estado final de CI se entregan en la
respuesta de cierre y quedan consultables en el PR. La publicación se realiza después
de aprobar los controles locales. La CI del repositorio repite pruebas, formatos,
contratos y builds en Linux.

**Confirmación:** no se modificaron `backend/app/modules/statistics/`,
`backend/app/orchestration/analysis_inputs.py`, `backend/app/orchestration/analysis_service.py`,
`backend/app/shared/contracts.py`, los seis contratos v1.0.0 ni contratos TypeScript
generados. No se modificaron fórmulas, motor, catálogo, informes o gráficos.
