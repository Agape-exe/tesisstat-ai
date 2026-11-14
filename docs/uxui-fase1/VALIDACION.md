# UX/UI fase 1 — registro de validación

> Registro histórico de la primera entrega. Su composición de secciones fue rechazada en la revisión visual. La [corrección estructural y evidencia vigente](../uxui-correccion/VALIDACION.md) sustituye esas decisiones; la aceptación final del usuario sigue pendiente.

Fecha de referencia: 6 de noviembre de 2026 (America/Lima).

## Base anterior a cambios de código

- Worktree independiente: `redisenio-uxui-fase1`.
- Rama: `feat/redisenio-uxui-fase1`, creada desde `origin/develop` en `9aa937e` (PR #56).
- Copia original limpia en `fix/cierre-sesion-17a`; se preservan todos los worktrees.
- `git fetch origin` ejecutado. Revisados PR #35 y #50–#56; Statistics corresponde a Diegodpma.
- PR #35 fusionado; su commit de LangGraph `026d771` es antecesor de esta base.
- PR #53 abierto y en borrador; GitHub devuelve `MERGEABLE` durante esta revisión, distinto del estado informado inicialmente. No se modifica ni integra.
- `npm ci`: correcto; 10 vulnerabilidades moderadas preexistentes. Sin cambios de dependencias.
- `npm test`: 109 aprobadas, 24 archivos, 0 fallos.
- ESLint y Prettier: correctos.
- Generación de contratos y comparación Git: sin diferencias.
- `npm run build`: correcto, incluye TypeScript; 217 módulos.
- `npm run build:research`: correcto; 208 módulos.
- `uv sync --locked`: correcto. **417 pruebas backend aprobadas**, 0 fallos, en 264.31 s; ejecución iniciada sobre la base antes de cambios frontend. Backend y contratos permanecieron intactos. Ruff y su formato correctos (142 archivos).

## Decisiones de integración

- Referencia HTML tratada como guía visual, no como instrucciones ni código de producción.
- Conservación de ProjectForm, validación y servicio CRUD HTTP existentes.
- Navegación mediante URL con fragmento para conservar los enlaces existentes y admitir F5 sin requerir reglas nuevas del servidor.
- Asistente como entrada del proyecto, independiente de la disponibilidad de materiales.
- Documentos/metodología y paquete/análisis/resultados/informes conservarán sus componentes funcionales durante la migración; se explicará la agrupación en pantalla.
- Instrumento se presenta como pendiente sin simular extracción, validación o confiabilidad.
- Sin cambios de motor, contratos, autorización, LangGraph ni PR #53; sin inferencias Qwen3.


## Entrega funcional de fase 1

Mis investigaciones, creación/edición y Asistente IA son funcionales y usan FastAPI/SQLite mediante los servicios existentes. La búsqueda filtra título, descripción, universidad y programa; se ordena por actualización o nombre. La navegación por URL funciona con F5, Atrás y Adelante y conserva los enlaces previos (`section=package` abre Análisis).

Componentes nuevos:

- `ProjectShell.tsx`: navegación principal, menú móvil, salto al contenido, `ProjectHeader` y `EmptyState`.
- `ProjectList.tsx`: tarjetas, búsqueda, orden y estados vacíos.
- `ProjectWorkspace.tsx`: integración y conservación de paneles visitados, aislados por clave de proyecto.
- `navigation.ts`: rutas por proyecto/sección y suscripción con `useSyncExternalStore`.
- `redesign.css`: tokens, tarjetas, controles, estados, diálogos, responsive y fondo blanco para dispersión.

Se modificaron `ResearchProjects` (coordinación CRUD/rutas/carga/errores), `ConversationChat` (accesos a materiales, fuentes desplegables, advertencias visibles y scroll limitado al historial), `app/styles.css`, sus pruebas y la concurrencia de Vitest. No hay nuevas dependencias.

Se reutilizan sin modificar ProjectForm, validación, servicio de proyectos, DeleteProjectDialog, ProjectDocuments, DocumentMethodology, ProjectDatasets, ProjectPackage y ProjectAnalysis. No hay cambios en Statistics, backend, fórmulas, contratos, LangGraph ni resultados existentes.

## Diferencias respecto al prototipo

1. El contrato exige título, universidad, programa y grado; descripción, facultad y año son opcionales. Se usa una pantalla de creación accesible con esos campos, en lugar del modal de dos campos del HTML.
2. El asistente conserva conversaciones reales, consentimiento, errores, trazas y agentes realmente utilizados. No se copian las respuestas simuladas del prototipo.
3. La bienvenida permite iniciar consultas generales sin materiales. Documentos y Datos abren sus cargas reales; Instrumento explica que está pendiente, sin extracción, validación ni confiabilidad ficticias.
4. Documentos y Metodología comparten el componente existente. Análisis, Resultados e Informes conservan el flujo integrado de paquete/análisis con explicación en pantalla. Consultar resultados no obliga a recalcularlos.
5. Se mantiene el aviso local sin autenticación. No se inventan perfiles, porcentajes de progreso ni estados fuera del contrato; los proyectos actuales tienen estado `draft`.

## Verificación final

| Comprobación | Resultado |
| --- | --- |
| Frontend `npm test` | **117 aprobadas**, 24 archivos, 0 fallos |
| ESLint y Prettier | Correctos |
| TypeScript (`tsc -b`, incluido en build) | Correcto |
| Generación de contratos y comparación Git | Sin diferencias |
| Build principal | Correcto, 222 módulos |
| Build Research independiente | Correcto, 213 módulos |
| Backend relevante tras implementar | **164 aprobadas**, 0 fallos, 110.29 s |
| Exportación de contratos `--check` y compilación Python | Correctas |
| `git diff --check` | Correcto |

Los 164 casos backend incluyen proyectos, conversaciones, contexto, multiagente y aplicación integrada. Los 417 casos de toda la suite se ejecutaron en la línea base; no se modificó backend después.

Las pruebas frontend nuevas cubren búsqueda, creación y apertura del chat sin documentos ni envíos automáticos, Atrás/Adelante, recuperación de Datos al remontar, enlace previo `package`, Metodología, Instrumento pendiente sin endpoints, descarte de respuestas tardías de otro proyecto y cierre de diálogos al cambiar el historial. Se conservan las pruebas existentes de errores CRUD, doble envío, consentimiento, recuperación de mensajes, aislamiento, fuentes, agentes y bloqueo de ejecución.

Las dos pruebas previas del recorrido se adaptaron a la navegación nueva. La prueba CRUD extensa se dividió conservando sus aserciones y agregando la comprobación de actualización. El fetch de las pruebas de página se aísla para no contactar servidores locales; los contratos HTTP tienen pruebas propias.

El paralelismo de jsdom causó timeouts intermitentes en Windows. `maxWorkers: 4` estabiliza la suite sin aumentar timeouts, omitir casos ni eliminar aserciones. Se comprobó primero con la opción de CLI y después con `npm test` normal.

## Evidencia en navegador

Historia observada: formulario React → API de proyectos → SQLite → asistente. Proyecto y conversación vacía seleccionada se recuperan tras recarga; el consentimiento vuelve a estar desmarcado. También se comprobó que una conversación creada en el proyecto 1 no aparece en el proyecto 2.

Se usaron el navegador integrado, Vite `127.0.0.1:5174` y el backend real `127.0.0.1:8011`, con credenciales deliberadamente vacías. Se preservaron los servicios previos en 8010/5173 y sus bases. No se hicieron llamadas a Qwen3 ni se activaron servicios de pago.

- Escritorio: 1366 × 900. Lista, búsqueda sin coincidencias, errores del formulario con foco en el primer campo, creación real, chat sin materiales y creación de conversación persistida.
- Recarga real y Atrás entre Documentos/Asistente: proyecto y selección recuperados. El envío sigue bloqueado sin proveedor, incluso al marcar consentimiento.
- Teclado: Enter en navegación y fuentes; salto al contenido sin cambiar la URL; diálogo nativo con foco inicial en Cancelar, cierre con Escape y restauración del foco a Eliminar investigación.
- Móvil: 390 × 844. Menú, cambio de sección con cierre del menú, campos claros y lista adaptada. `scrollWidth == clientWidth == 375` con 15 px reservados al scroll: sin desbordamiento horizontal.
- Consola inspeccionada: sin errores ni advertencias de aplicación observados.
- Campo de título: fondo `rgb(255,255,255)` y borde visible `rgb(189,184,208)`.
- Dispersión real de Resultados: cuatro pares autorizados recuperados por API; figura y SVG con fondo `rgb(255,255,255)`, sin divisiones negras. Solo cambió su presentación.

Bases ignoradas por Git: `backend/.cache/uxui-phase1` (creación/conversación) y `backend/.cache/uxui-phase1-figures` (dos proyectos sintéticos, uno vacío y otro con Pearson). La segunda se inicializó mediante el `scripts.demo_context_chat.seed` existente sobre `create_app` con credenciales vacías: revisión manual, aprobación explícita y ejecución determinista en la base de prueba. No se inyectó un proveedor ficticio en el servidor visual ni se alteraron datos de la usuaria. El frontend de producción no incorpora fixtures ni respuestas falsas.

La persistencia de mensajes poblados, las respuestas y las trazas de agentes se comprobaron en suites con proveedores inyectados sin red. En navegador se verificó una conversación persistida vacía; no se afirma haber observado inferencia real.

El navegador rechazó abrir el HTML de referencia mediante `file:`. Se revisó como texto, sin eludir ese bloqueo; la implementación local sí se verificó visualmente por HTTP.

Capturas reales:

- [Lista de escritorio](evidencia/mis-investigaciones-escritorio.jpg)
- [Lista móvil](evidencia/mis-investigaciones-movil.jpg)
- [Formulario claro](evidencia/nueva-investigacion.jpg)
- [Asistente](evidencia/asistente-escritorio.jpg)
- [Dispersión blanca](evidencia/dispersion-fondo-blanco.jpg)

## Riesgos y fase 2

- PR #53 permanece fuera de esta rama. La degradación de fuentes al vencer una autorización estadística continúa siendo un riesgo de la base; esta fase presenta lo que entrega el backend.
- Diez vulnerabilidades npm moderadas preexistentes; sin cambios de dependencias o lockfiles.
- El backend actual es local y no tiene autenticación; este rediseño no lo habilita para datos reales ni despliegue público.
- Los paneles visitados conservan borradores al alternar secciones dentro del proyecto. Editar o abandonar el proyecto y recargar conservan lo guardado en backend. Los recursos pendientes de guardar requieren guardar antes de salir, como indica el flujo existente.
- Fase 2: separar y rediseñar Documentos/Metodología y Análisis/Resultados/Informes; consolidar estilos heredados; definir contratos reales de Instrumento antes de implementarlo. Quedan pendientes una auditoría de accesibilidad completa y revisión visual con historial poblado del modelo.
- No se inicia Sesión 18A. Esta entrega completa únicamente la fase 1.

## Publicación

Antes de publicar se volvió a consultar `origin/develop`: `9aa937e`, sin avances desde el PR #56. No hubo merges, rebases, resets destructivos ni force push. Rama independiente, PR en español hacia `develop`, sin fusionar ni añadir coautores, revisores o asignados.
