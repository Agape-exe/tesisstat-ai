# feat: implementar orquestación multiagente con LangGraph

La integración de GitHub devolvió 403 `Resource not accessible by integration` al crear
el PR. La rama está publicada. Crear manualmente con base **develop** y comparación
**feat/orquestacion-multiagente**:

[Crear el PR hacia develop](https://github.com/Agape-exe/tesisstat-ai/compare/develop...feat/orquestacion-multiagente?expand=1)

Copiar el título anterior y la descripción siguiente. No fusionar automáticamente.

## Objetivo
Transformar el chat contextual de las sesiones 15A/16A en un sistema multiagente real, coordinado localmente mediante LangGraph 1.2.19, conservando la persistencia SQLite y el proveedor Qwen3/Cloudflare existente.

## Agentes y rutas
- Conversación: prepara contexto e historial, realiza como máximo una llamada al proveedor y valida la respuesta.
- Investigación: recupera fuentes académicas verificadas, sus versiones y advertencias mediante ResearchContextBuilder.
- Planificación estadística: consulta el paquete vigente y reutiliza el planificador determinista y las validaciones actuales, sin persistir propuestas.
- Pregunta general: enrutador → conversación.
- Metodología, datos o resultados: enrutador → investigación → conversación.
- Planificación: enrutador → investigación → planificación → conversación.
- Solicitud de ejecución/modificación: enrutador → conversación con bloqueo; el grafo no tiene acceso al motor.

StateGraph usa nodos y transiciones condicionales reales. Las pruebas observan los updates del grafo compilado, además de las trazas persistidas.

## Integración y seguridad
Se mantienen los endpoints, consentimiento ampliado, historial, F5, idempotencia, concurrencia, separación por proyecto y errores de Cloudflare. Message.context añade una traza compatible y el chat muestra solamente los agentes participantes.

La lectura del contexto evita las escrituras de invalidación de ResearchAnalysisService.list(): consulta el repositorio y reutiliza el validador interno de solo lectura _current(record). Mantiene verificación de procedencia, versiones y tokens. No modifica Statistics, analysis_inputs.py, analysis_service.py, fórmulas, catálogo, informes, gráficos ni los seis contratos v1.0.0.

Las propuestas son orientativas en memoria, sin aprobación ni ejecución. Hay límites configurables de pasos, llamadas, planificación, contexto, salida y tiempo. El deadline es cooperativo y no interrumpe operaciones CPU-bound. LangSmith no se contrata y el trazado externo se deshabilita explícitamente.

## Presupuesto
S/ 0 de servicios consumidos; cero llamadas a Qwen3 real durante implementación, pruebas y demo. Máximo una operación chat() por turno completado; cero llamadas del enrutador, Research y Planning. No hay reintentos automáticos ni proveedor nuevo.

## Verificación
- Backend: 385 pruebas aprobadas; 47 casos nuevos de multiagente.
- Verificación final de Conversation/contexto/multiagente: 131 aprobadas.
- Ruff check y formato: correctos; 139 archivos con formato válido.
- uv sync --locked, importación de la aplicación, compilación Python y validación de contratos: correctos.
- Frontend: 99 pruebas aprobadas en 19 archivos.
- ESLint, Prettier, TypeScript y generación de contratos: correctos.
- Build principal: 210 módulos; build Research independiente: 201 módulos.
- Navegador: escenarios A–D, consentimiento, agentes y recuperación de historial tras recarga con proveedor simulado; consola sin errores/advertencias.
- git diff --check y comparación de archivos protegidos: correctos.
La CI del PR confirmará estos controles también en Linux.

## Demostración
Desde backend/: `uv run python -m scripts.demo_multiagent`. Ejecuta los cuatro escenarios con fuentes sintéticas y proveedor identificado como simulado, sin red ni ejecución estadística.
Interfaz: backend demo en 8017 y frontend en 5177. Instrucciones completas en docs/ORQUESTACION_MULTIAGENTE.md y docs/INFORME_SESION_17A.md.

## Limitaciones y pendientes
Enrutamiento por reglas conservadoras; hipótesis ambiguas y fuentes incompletas requieren aclaraciones. El lector depende del validador interno _current y debe revisarse si esa interfaz cambia. No hay nuevo checkpointer, autenticación multiusuario, creación de planes desde el chat ni ejecución automática.
Pendiente validación humana del recorrido y calidad de respuestas con Qwen3 real dentro de la cuota gratuita. Las ampliaciones de enrutamiento y un eventual flujo explícito de creación de planes se reservan para sesiones posteriores.

No fusionar automáticamente.
