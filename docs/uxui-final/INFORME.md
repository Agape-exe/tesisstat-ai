# TesisStat AI — entrega local del rediseño de las siete pantallas

6 de noviembre de 2026, America/Lima. Rama `feat/redisenio-uxui-fase1`, PR #57. **Lista para revisión visual de Melissa; no publicada ni fusionada.**

Abrir la [galería](REVISION_VISUAL.html) o la [galería servida por HTTP local](http://127.0.0.1:8021/docs/uxui-final/REVISION_VISUAL.html). [React local](http://127.0.0.1:5179/) utiliza FastAPI en `127.0.0.1:8022`, SQLite y archivos de QA independientes. Los procesos anteriores en 5178/8018 y la evidencia anterior se conservaron.

## A. Referencias y comparación visual

No faltan referencias. Se localizaron, abrieron e inspeccionaron:

- `C:/Users/Melissa/Downloads/TesisStat_AI_Mockup_Integral_Corregido.html`, SHA-256 `60dac57527076a1468c42b403924211e05c29587d329c512cd87c4d8dd73620b`.
- `docs/uxui-fidelidad/REVISION_VISUAL.html`, conservada en el respaldo aprobado.
- Las siete capturas originales de `C:/Users/Melissa/Downloads/tesisstat-ai-mockup-integral.zip`. Las copias entregadas coinciden byte por byte con las entradas originales del ZIP; [manifest de referencias](referencias.json).
- La implementación local aprobada de Mis investigaciones y Asistente IA, respaldada primero en `ea7cd85`.

La galería contiene **21 comparaciones**, siete pantallas por tres tamaños: **1440 × 900, 1366 × 768 y 390 × 844**, dispositivo a escala 1. Cada PNG comparativo une dos capturas nativas sin escalarlas y añade 36 px para las etiquetas. Incluye capturas completas de escritorio y móvil, las siete referencias originales y catorce capturas adicionales de estados vacíos.

[Geometría de React y mockup](geometria.json): en escritorio se reproduce el área de contenido de 1080 px, los márgenes adaptativos y la columna de apoyo de 295 px; en móvil las columnas se apilan, las tablas y pestañas tienen desplazamiento local y ninguna de las siete pantallas desborda horizontalmente el documento. Se inspeccionaron jerarquía, tipografía, espaciados, disposición, navegación secundaria, tablas, gráficos, controles y acciones principales. Compartir colores no fue el criterio de validación.

**Preservación de las pantallas aprobadas:** comparación contra un worktree temporal detached del respaldo `ea7cd85`, utilizando el mismo backend, datos, viewport, idioma y estado. La corrida final dio **cero píxeles distintos en las seis comparaciones**: dos pantallas por tres tamaños. [Evidencia](preservacion-aprobadas.json). Las corridas iniciales presentaron variaciones de rasterización de un nivel por canal en algunos bordes móviles; la comparación final normaliza la posición del puntero. Los archivos de conversación, listado y sus estilos aprobados no tienen diferencias respecto al respaldo.

## B. Informe UX/UI y diferencias explícitas

`SectionLayout`, `SupportPanel`, `Guidance`, `sectionInfo` y `sections.css` proporcionan la composición compartida de las herramientas. El encabezado académico anterior se sustituye por título de sección, descripción, breadcrumb y navegación secundaria. Los estilos nuevos se limitan a esas herramientas; la barra lateral aprobada y el asistente se conservan.

| Pantalla | Estructura implementada | Diferencia justificada respecto a la referencia |
| --- | --- | --- |
| Documentos | Título y acción principal; área de carga; archivos con formato, tamaño y estado; extracción solo al seleccionar; columna de orientación. | La lista de la API no incluye el estado de extracción. Se presenta «Por consultar» hasta consultarlo, conservando los estados ya leídos. La carga y las acciones reales añaden altura. No se inventan descarga o visualización del archivo original que la API no ofrece. |
| Metodología | Lectura por Objetivos, Variables y dimensiones e Hipótesis; editor mediante acción explícita; fuente, diseño, versiones y extracción avanzada bajo demanda. | Las advertencias reales de campos pendientes y las decisiones de guardar/confirmar añaden espacio. Se conserva el modelo completo, incluyendo campos que no aparecen en la maqueta simplificada. |
| Instrumento | Composición con estado pendiente y explicación académica; acceso claramente identificado al almacenamiento documental. | No se reproducen los ítems y escalas ficticios de la maqueta como detecciones reales. La interpretación estructurada continúa pendiente y no se inicia 18A. |
| Datos | Archivo activo antes de las pestañas, dimensiones y origen visibles, tabla legible; Calidad y Preparación separadas; administración y procedencia bajo demanda. | Se mantienen las tres vistas exigidas. La correspondencia se edita en las vinculaciones de Análisis. Seleccionar otro archivo abre la carga real sin ocupar permanentemente la vista previa. |
| Análisis | Preparación visual, plan y ejecución independientes; editor avanzado explícito; técnica, justificación, supuestos, aclaraciones y aprobación reales. | Tres etapas según esta solicitud, frente a cuatro pasos conceptuales del HTML. La técnica procede del planificador: Pearson aparece solo porque la muestra sintética y su configuración lo permiten. |
| Resultados | Historial compacto seleccionable; resumen de métricas; interpretación lateral; gráfico de observaciones mediante acción autorizada; comprobaciones y valores originales. | Se añaden historial, vigencia y advertencias reales. La muestra perfecta de QA genera `r=1`, un estadístico extremo y `p_value=0` registrado: el aviso de precisión ocupa espacio adicional. Todas las métricas, también las extremas, permanecen en «Valores originales y precisión». |
| Informes | Selección del análisis de origen, resumen de sus métricas e interpretación, exportaciones y restricciones en una columna propia. | No existe una previsualización del documento final ni un catálogo de exportaciones persistidas en la API. Se muestra un resumen del resultado real; PDF/DOCX se generan al descargar. No se copia el informe ilustrativo de la maqueta. |

Los gráficos conservan fondo blanco uniforme mediante estilos de la pantalla de Resultados. No se modificaron los componentes de Statistics ni sus fórmulas. Los tipos técnicos de columnas no se convierten en escalas estadísticas.

## C. Informe funcional

[Recorrido y solicitudes HTTP](funcional.json), **13 comprobaciones** contra React, FastAPI y SQLite reales:

1. Crear una investigación sintética desde el listado y abrir el asistente.
2. Enviar una solicitud consentida al proveedor simulado local; cero ejecuciones desde el chat. Tras F5 se recupera el mensaje y se vuelve a solicitar consentimiento.
3. Cargar DOCX, extraer su texto mediante el servicio real y recuperar el documento tras F5.
4. Abrir el editor metodológico, guardar, recargar y recuperar los valores.
5. Confirmar de forma explícita y navegar por las tres vistas metodológicas.
6. Comprobar Instrumento pendiente, sin detecciones ni cálculos simulados.
7. Cargar CSV, declarar origen sintético, activarlo y consultar tabla y EDA reales.
8. Seleccionar una transformación, previsualizar, confirmar, crear un derivado y recuperar su historial tras F5. La activación del derivado sigue siendo una decisión separada.
9. Preparar la investigación y solicitar un plan; un intento directo sin aprobar recibe **409**, sin crear resultados.
10. Aprobar el plan, recargar, ejecutar mediante su botón y obtener un único resultado.
11. Descargar PDF y DOCX reales, verificar sus firmas y comprobar que no cambian los resultados ni se recalcula.
12. Modificar y confirmar metodología: el objeto de resultado conserva exactamente sus métricas e interpretación; el historial sigue disponible y la exportación queda bloqueada por vigencia.
13. Consultar otro proyecto vacío y verificar aislamiento.

La configuración inicial de la fixture metodológica y las vinculaciones se preparó por los endpoints públicos existentes. El objetivo vinculado se seleccionó y guardó desde el editor real antes de validar y construir el paquete. Durante la preparación, el backend rechazó correctamente una vinculación a un objetivo que ya había cambiado; se corrigió la fixture desde el editor, sin modificar validaciones.

[Comprobaciones complementarias](estados-y-eliminacion.json): estados vacíos de las siete pantallas en escritorio/móvil; error 503 de lectura inyectado solo en el navegador de QA y recuperación; rechazo de formato documental inválido; cancelación y confirmación de eliminación de documentos/datasets temporales, con persistencia tras F5. Se añadió regresión de selección de dataset eliminado para evitar consultar un ID antiguo al restaurar una URL.

[Red y consola durante las capturas](red-capturas.json): cero errores JavaScript y cero solicitudes a destinos externos. El servidor de QA se construye con credenciales vacías y `DemoProvider` local. No se realizaron llamadas externas a Qwen3 ni se usaron datos académicos reales. Los scripts y las descargas auténticas de QA están en [qa](qa/).

Continúan pendientes únicamente las capacidades de backend descritas en la tabla: interpretación estructurada de instrumentos y previsualización/archivo persistido de exportaciones. No se presentan como implementadas.

## D. Pruebas y verificaciones

| Verificación | Resultado | Evidencia |
| --- | --- | --- |
| Vitest completo | **155/155**, 26 archivos, un worker en Windows | [Registro](frontend-pruebas.log) |
| Backend: todos los tests Research y contratos | **342/342**, cero fallos | [Registro](backend-pruebas.log) |
| ESLint | Correcto, cero advertencias | [Registro](eslint.log) |
| Prettier frontend | Correcto | [Registro](prettier.log) |
| TypeScript `tsc -b` | Correcto; también ejecutado por build principal | [Registro](typescript.log) |
| Generación de contratos frontend | Correcta, sin diferencias en generados | [Registro](contratos-frontend.log) |
| Contratos backend `export_contracts --check` | Correctos, sin modificar contratos | [Registro](contratos-backend.log) |
| Build principal | Correcto | [Registro](build-principal.log) |
| Build Research | Correcto; aviso informativo de bundle >500 kB | [Registro](build-research.log) |
| Ruff y formato backend | Correctos, 138 archivos con formato conservado | [Lint](ruff.log), [formato](ruff-formato.log) |
| `git diff --check` | Correcto | Comprobado antes de los commits |


Las regresiones conservan las aserciones de servicios, navegación, guardado, confirmación, permisos e historial. Los cambios de pruebas reflejan pestañas, controles bajo demanda y selección del dataset activo. No se ampliaron timeouts ni se desactivaron validaciones. Se incorporaron pruebas de precisión numérica, respuestas de extracción tardías y selección de dataset eliminado.

Comandos de verificación: `npm test -- --maxWorkers=1 --reporter=dot`, `npm run lint`, `npm run format:check`, `npx tsc -b`, `npm run contracts:generate`, `npm run build` y `npm run build:research`. En backend: `python -m pytest tests/research tests/test_contracts.py -q`, `python -m scripts.export_contracts --check`, `ruff check app tests` y `ruff format --check app tests`.

El build Research mantiene un aviso informativo de bundle superior a 500 kB; termina correctamente. No se cambiaron dependencias para este rediseño final.

## E. Git y revisión remota

- Worktree: `C:/Users/Melissa/Desktop/tesisstat-ai/redisenio-uxui-fase1`.
- Rama activa: `feat/redisenio-uxui-fase1`. HEAD inicial: `d6aebb280775983f9ee04dfae321dbb118b0986c`.
- `ea7cd85`: **respaldo: conservar corrección aprobada de investigaciones y asistente IA**. Se creó antes de modificar las siete pantallas e incluye los cambios locales y la evidencia anteriores.
- `5f18678`: **feat: finalizar rediseño de las siete pantallas de investigación**. Implementación y regresiones.
- `7476ff0`: **fix: conservar las etapas de análisis en una fila en móvil**. Corrección visual puntual detectada al inspeccionar la comparación móvil.
- Commit documental adicional: **docs: entregar comparación visual y validación final del rediseño**, que contiene esta entrega.
- Estado al finalizar: cuatro commits locales por delante del remoto; árbol de trabajo limpio. Los artefactos temporales de QA están excluidos en `.cache`.
- `git fetch origin` ejecutado al inicio y al cierre. `origin/develop` sigue en `9aa937ede037e3a7801557a87597632a05063947`; `origin/feat/redisenio-uxui-fase1` sigue en `d6aebb2`.
- Se revisaron los cambios integrados del compañero de Statistics, incluidos el arreglo del bucle de consultas de demo (`75bc5d3`) y las figuras de pares autorizadas (`2d0f4a3`), ya incluidos en develop. No se modificaron.
- [PR #57](https://github.com/Agape-exe/tesisstat-ai/pull/57): abierto, sin fusionar, remoto en `d6aebb2`. Su CI no valida estos commits locales aún no publicados. No se cambiaron título, descripción, comentarios ni estado.
- [PR #53](https://github.com/Agape-exe/tesisstat-ai/pull/53): abierto en borrador, HEAD `f445957`; sin modificar ni integrar.
- Sin diferencias en backend, Statistics, contratos, servicios API, conversación aprobada, `ProjectList`, `ResearchProjects` ni `redesign.css` respecto al respaldo. Los cambios de `ProjectShell` se limitan al encabezado de herramientas y su importación de metadatos; `ProjectWorkspace` incorpora la presentación de Instrumento.
- No hubo push, force push, merge, rebase, reset ni modificaciones directas en main/develop. La copia detached del respaldo se utiliza solo para comparación visual.


La galería y este informe permiten revisar las diferencias antes de autorizar una publicación. Esta entrega no sustituye la aprobación visual de Melissa.
