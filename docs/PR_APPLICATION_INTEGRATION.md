# PR preparado para develop

Título: `feat: unify local application and export persisted analysis reports`

Rama origen: `feat/application-integration` · Destino: `develop` · Estado recomendado:
listo para revisión tras la validación manual confirmada por la usuaria.

La entrada principal todavía mostraba la base de la sesión 1. Ahora reutiliza los
formularios reales de Research y organiza el recorrido en documento/metodología,
datos/EDA/preparación y paquete/análisis/resultados, con una sola API local.

ProjectAnalysis concentra propuesta, revisión, aprobación explícita y ejecución.
ResearchStatisticsPanel delega en él. Los históricos siguen visibles con acciones
bloqueadas cuando las fuentes cambian. La declaración de origen sintético se realiza
antes de preparar derivados.

Las descargas DOCX/PDF leen exclusivamente AnalysisResult persistidos, aprobados,
completados y vigentes, verificando proyecto, plan y dataset. No admiten métricas del
cliente ni recalculan. Se reutilizan los generadores de Statistics; el PDF pagina sin
truncar y conserva español mediante WinAnsi, con aviso para caracteres no representables.
Sin cambios en fórmulas, motor, app.main ni los seis contratos v1.0.0.

Validación local: 235 pruebas backend, 66 frontend; Ruff check/format, ESLint, Prettier,
contratos, compileall, TypeScript, build principal (incluye Statistics) y Research
independiente correctos. Los builds consecutivos conservan las tres entradas. E2E HTTP
real con DOCX, metodología manual, CSV, EDA, derivado, paquete, descriptivos/Pearson,
aprobación, persistencia tras reinicio y exportaciones. La descarga no invoca el motor.
PDF real y largo de tres páginas inspeccionados; DOCX reabierto y contenido verificado.

El seguimiento manual añade sincronización de la versión del formulario después de
generar un paquete y ordena los planes del más reciente al más antiguo. Dos pruebas de
regresión cubren la edición posterior a la generación y la posición del plan vigente.

La usuaria confirmó el recorrido manual completo el 2 de noviembre de 2026, incluidos
los cálculos descriptivos y Pearson, la aprobación obligatoria, la persistencia tras F5,
las descargas DOCX/PDF visualmente correctas y los bloqueos de aclaraciones, obsolescencia
y archivo vacío. El agente no pudo completar su propia navegación por un bloqueo de su
herramienta; esta confirmación manual procede de la usuaria.

CI de la corrección `bcb0eba` aprobada:
[Foundation checks](https://github.com/Agape-exe/tesisstat-ai/actions/runs/41421516566).
Instrucciones de inicio, datos ficticios y límites en
[APPLICATION_INTEGRATION.md](APPLICATION_INTEGRATION.md).

No fusionar automáticamente. Demo exclusivamente local, sin despliegue público ni
llamadas a Cloudflare.

## Publicación

La rama está publicada. El intento de crear el PR mediante el conector GitHub devolvió
`403 Resource not accessible by integration`. No se intentó otro mecanismo para eludir
la restricción. Este archivo conserva el contenido para su revisión y creación manual
por una persona con permisos.
