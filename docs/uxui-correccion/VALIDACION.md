# Corrección estructural UX/UI de la fase 1

Fecha: 6 de noviembre de 2026. PR: [#57](https://github.com/Agape-exe/tesisstat-ai/pull/57).

La corrección está implementada y verificada localmente. La aceptación visual final corresponde al usuario; el PR debe permanecer sin fusionar. Este registro sustituye las decisiones de composición de secciones del primer registro de fase 1, cuyo resultado visual fue rechazado.

## Base y preservación

- Rama existente `feat/redisenio-uxui-fase1`, conservando `d846444` y sus antecesores.
- Working tree limpio al empezar; trabajo en el worktree `redisenio-uxui-fase1`. Se preservan las otras ramas y copias locales.
- `git fetch origin` antes del trabajo y nuevamente antes de publicar. `origin/develop`: `9aa937e`, PR #56. Integra el cierre 17A y LangGraph ya existentes.
- Revisados PR #53 y cambios recientes de Statistics (#54–#56). No se modifica ni integra #53. No se realizan merges, rebase, reset destructivo ni force push.
- No hay cambios en backend, contratos, Statistics, fórmulas, LangGraph, consentimiento ni dependencias. No se inicia 18A.

## Arquitectura de información

Se elimina `panelFor()` y sus equivalencias entre menús. `ProjectWorkspace` compone una vista propia por sección y conserva las vistas visitadas para mantener borradores al cambiar de sección. Las lecturas se actualizan al volver; las respuestas tardías no sustituyen información de otro proyecto. La URL identifica proyecto, sección, vista interna y elemento seleccionado.

| Sección | Tarea principal y componentes | Operaciones reales conservadas |
| --- | --- | --- |
| Documentos | `ProjectDocuments`: cargar/listar archivos, consultar y extraer texto | CRUD y extracción existentes; acceso a Metodología |
| Metodología | `ProjectMethodology`: resumen de objetivos, hipótesis, variables y dimensiones | Estado, creación manual, `ReviewEditor`, guardado y confirmación; extracción IA opcional con consentimiento existente |
| Datos | `ProjectDatasets`: archivo/vista previa, calidad o preparación, una vista a la vez | Carga CSV/XLSX, procedencia/activación, `DatasetEDA`, `DatasetPreparation`, previsualización y confirmación segura de derivados |
| Análisis | `AnalysisWorkspace`: preparación → plan → ejecución | Resumen desde `packageApi.status`; editor explícito `ProjectPackage` con save/validate/build; `ProjectAnalysis` propone y aprueba; `ExecutionStage` ejecuta únicamente planes aptos |
| Resultados | `ProjectResults` + `ResultDetail`: seleccionar y consultar resultados persistidos | Métricas, supuestos, interpretación, avisos y gráficos existentes; historial incluso con fuentes desactualizadas |
| Informes | `ProjectReports`: seleccionar origen y descargar formato | PDF/DOCX existentes desde resultados guardados; sin recalcular, archivo persistido o previsualización inventada |
| Asistente | `ConversationChat` existente | Conversaciones, mensajes, consentimiento y aislamiento sin cambios |
| Instrumento | Estado pendiente explícito | Sin extracción de ítems, validez ni confiabilidad simuladas |

`ProjectPackage` ya no renderiza análisis. `ProjectAnalysis` ya no contiene ejecución, resultados ni exportaciones. `ResultDetail` reutiliza los gráficos y la presentación de resultados existentes sin modificar los cálculos. Los hooks `useReadResource`, `useResearchPackage`, `useAnalysisPlans` y `useAnalysisHistory` separan lecturas, acciones y errores.

El historial se consulta independientemente del estado de las fuentes. Si falla su verificación, se conservan las métricas guardadas y se bloquean exportaciones y observaciones autorizadas. La ejecución exige aprobación explícita, vigencia, plan ejecutable, ausencia de resultado previo y autorización de datos no sintéticos; el backend vuelve a comprobarlo. Los informes conservan sus análisis de origen después de invalidarse, con descarga deshabilitada.

## Línea base y pruebas finales

La línea base anterior a modificar esta corrección fue de 116/117 pruebas frontend: `DatasetPreparation` superó el timeout preexistente de 5 segundos con cuatro workers en Windows. Backend pertinente: 165/165. Se conserva el timeout y las aserciones; Vitest usa ahora dos workers para reducir contención.

Verificaciones finales:

- Frontend: **131/131 pruebas aprobadas**, cero fallos, con `npm test` y el límite normal de dos workers.
- Se prueban expresamente la ausencia de preparación en Resultados; ausencia de propuesta/ejecución en Informes; composición distinta de Metodología; persistencia de guardados tras remontar y navegar; Atrás/Adelante en Datos; conservación de borradores entre secciones; denegación de ejecución sin aprobación/autorización; historial desactualizado o con error de fuentes; denegación de exportación; estados vacíos y resultados fallidos. Se conservan las aserciones de vinculación, versiones, aprobación, métricas y gráficos existentes.
- Backend: **165/165 pruebas aprobadas** (112.62 s): `test_analysis_e2e`, `test_application_integration`, `test_projects`, `test_packages`, `test_methodology_review`, `test_preparation`, `test_conversation`, `test_data_authorization`.
- ESLint sin advertencias, Prettier, TypeScript y Ruff correctos; formato backend: 142 archivos sin cambios.
- Exportación backend de contratos con `--check` y generación frontend correctas, sin diferencias en contratos generados.
- Build principal y build Research independiente correctos (234 y 225 módulos respectivamente).
- Sin relajación de restricciones de Statistics ni datos falsos en producción. Las respuestas simuladas de pruebas unitarias permanecen exclusivamente en pruebas.

## Verificación real en navegador

API FastAPI local independiente en `127.0.0.1:8011`, Vite en `127.0.0.1:5174`, SQLite de QA bajo `.cache/uxui-structural`. Se utilizan exclusivamente datos ficticios y sintéticos. No se envían mensajes al modelo, no se llama a Qwen y no se activan servicios de pago. Los servidores originales del usuario no se reemplazan.

1. Crear investigación mediante API desde el formulario y abrir su asistente vacío: bienvenida y accesos, sin afirmar lectura de documentos inexistentes.
2. Abrir proyecto sintético con fuentes; Documentos muestra archivo y extracción real de texto, sin editor metodológico incrustado.
3. Metodología muestra su revisión y editor propio. Se guarda y confirma un cambio real al objetivo metodológico.
4. Datos: vista previa real de cuatro filas, EDA existente y preparación; se previsualiza eliminación de duplicados sin aplicar el derivado. Se comprueba el control de confirmación.
5. Análisis abre primero el resumen. El formulario de vínculos aparece únicamente al abrir su editor y tiene regreso al resumen.
6. Seleccionar hipótesis, proponer un nuevo plan real, aprobar explícitamente, recuperar el plan aprobado tras F5 y ejecutar una vez.
7. Resultados recupera las dos ejecuciones persistidas del proyecto, permite seleccionar resultados y consultar dispersión autorizada con fondo blanco, sin formulario de preparación.
8. Informes descarga PDF y DOCX reales. El registro HTTP confirma una propuesta, una aprobación y una ejecución nuevas, y dos GET de exportación; no hay ejecución estadística por descargar.
9. Tras guardar/confirmar el cambio de metodología, el backend invalida la vigencia. F5 conserva ambos resultados históricos y bloquea observaciones/exportaciones. Se comparan los dos objetos completos `result` antes y después: permanecen idénticos. No se recalcula para recuperar el historial.
10. Proyecto sin fuentes: Análisis incompleto, Resultados e Informes vacíos. Navegación por historial (Atrás/Adelante), F5 y menú móvil comprobados; no hay desbordamiento horizontal del documento en las vistas móviles revisadas. Las tablas conservan desplazamiento interno.

La aprobación, denegación de autorización, errores de API y restricciones adicionales tienen regresión automatizada. No se afirma haber ejecutado en navegador un análisis con datos reales: la comprobación visual usa solo datos sintéticos. El asistente y consentimiento conservan su regresión automatizada; no se realiza inferencia real durante esta corrección.

## Evidencia visual

Las capturas corresponden a la aplicación React y API locales reales. El HTML aprobado se usa como referencia, sin copiar sus scripts ni tratar su contenido como instrucciones.

| Pantalla | Capturas |
| --- | --- |
| Análisis | [Resumen](evidencia/analisis-preparacion.jpg), [plan](evidencia/analisis-plan.jpg), [ejecución aprobada](evidencia/analisis-ejecucion.jpg), [editor explícito](evidencia/editor-vinculaciones.jpg), [fuentes desactualizadas](evidencia/analisis-desactualizado.jpg), [incompleto](evidencia/analisis-incompleto.jpg) |
| Resultados | [Resultado persistido](evidencia/resultados.jpg), [dispersión](evidencia/resultados-dispersion.jpg), [historial desactualizado](evidencia/resultados-desactualizados.jpg) |
| Informes | [Exportación disponible](evidencia/informes.jpg), [descarga bloqueada por vigencia](evidencia/informes-bloqueados.jpg) |
| Metodología | [Revisión independiente](evidencia/metodologia.jpg) |
| Datos | [Archivo/vista previa](evidencia/datos-vista-previa.jpg), [calidad](evidencia/datos-calidad.jpg), [preparación segura](evidencia/datos-preparacion.jpg) |
| Responsive | [Datos móvil](evidencia/datos-movil.jpg), [Análisis móvil](evidencia/analisis-movil.jpg) |

## Diferencias y pendientes

- Se mantienen los controles avanzados del editor real de vinculaciones y revisión. Algunos valores técnicos del backend permanecen dentro del editor o detalles desplegables; las vistas principales tienen resúmenes propios. Los errores y advertencias necesarias no se ocultan, aunque incluyan referencias técnicas del backend.
- No se inventan archivo de informes, previsualización de documentos finales, métricas ni interpretaciones. La API actual entrega las exportaciones al descargarlas.
- El historial guardado se recupera desde la API tras F5. Los borradores sin guardar se conservan al cambiar de sección, pero no se promete conservarlos tras recargar; deben guardarse mediante el editor existente.
- Sin cambios de dependencias; se mantiene el reporte previo de diez vulnerabilidades npm moderadas. El entorno local sigue mostrando su advertencia existente de ausencia de autenticación.
- Pendientes de fase 2: refinamiento visual completo de los editores avanzados y demás pantallas, tras la revisión del usuario; Instrumento continúa pendiente y requiere un alcance posterior. No se inicia 18A.
- La validación automatizada y visual técnica no sustituye la aceptación del usuario. PR #57 debe permanecer abierto y sin fusionar hasta esa revisión.
