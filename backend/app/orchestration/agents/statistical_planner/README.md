# Statistical Planner Agent

Implementado en `agent.py`, como nodo `planning` del grafo LangGraph de la Sesión 17A.
Su puerto `VerifiedPlanningReader` verifica proyecto, fuentes, metodología confirmada,
dataset y paquete vigentes. Reutiliza `DeterministicStatisticalPlanner.propose()` y las
validaciones metodológicas existentes de `analysis_inputs`, sin modificar Statistics.

Produce una propuesta orientativa en memoria o aclaraciones. No persiste planes, no
aprueba, no calcula métricas y no ejecuta el motor. Los planes registrados y resultados
anteriores se consultan mediante el contexto de Research, con su estado y procedencia.

Ver [arquitectura y demo](../../../../../docs/ORQUESTACION_MULTIAGENTE.md).
