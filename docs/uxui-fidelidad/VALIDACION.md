# Corrección visual local para revisión — PR #57

Fecha: 6 de noviembre de 2026, America/Lima. **Pendiente de aprobación visual de Melissa. Sin publicar, sin commit nuevo y sin fusionar.**

Abrir la [galería de capturas](REVISION_VISUAL.html) o la [aplicación React local](http://127.0.0.1:5178/). La aplicación usa una API aislada en `127.0.0.1:8018`, SQLite de QA y el proveedor simulado existente del backend. No realiza inferencia Qwen3 ni transmite los mensajes a Cloudflare. Los procesos originales en 5173, 5174 y 8011 se preservaron.

## A. Referencias y comparación visual

Se leyó el HTML corregido y se inspeccionaron las capturas del ZIP. Se usaron como referencias visuales; no se incorporaron sus scripts, respuestas simuladas ni almacenamiento al frontend.

- HTML principal: `C:/Users/Melissa/Downloads/TesisStat_AI_Mockup_Integral_Corregido.html`.
- SHA-256 HTML: `60DAC57527076A1468C42B403924211E05C29587D329C512CD87C4D8DD73620B`.
- ZIP complementario: `C:/Users/Melissa/Downloads/tesisstat-ai-mockup-integral.zip`.
- SHA-256 ZIP: `BD6D0D6B24BDF5C6F018A3867A35DB37F77B4EEA6856DB811DD0BBA4B10CA9B9`.
- Capturas originales del ZIP: [Inicio](evidencia/referencia-zip-inicio.png), [Asistente](evidencia/referencia-zip-asistente.png).

Las comparaciones se capturaron en Chromium, con escala de dispositivo 1 y **el mismo viewport para HTML y React**: 1440 × 900, 1366 × 768 y 390 × 844. Cada imagen comparativa une dos capturas a tamaño original, sin redimensionarlas; añade únicamente 36 px para las etiquetas. Las capturas individuales conservan exactamente las dimensiones solicitadas.

| Vista | 1440 × 900 | 1366 × 768 | 390 × 844 |
| --- | --- | --- | --- |
| Mis investigaciones, lado a lado | [Comparar](evidencia/comparacion-investigaciones-1440.png) | [Comparar](evidencia/comparacion-investigaciones-1366.png) | [Comparar](evidencia/comparacion-investigaciones-390.png) |
| Asistente con mensajes, lado a lado | [Comparar](evidencia/comparacion-asistente-1440.png) | [Comparar](evidencia/comparacion-asistente-1366.png) | [Comparar](evidencia/comparacion-asistente-390.png) |
| Asistente sin materiales, lado a lado | [Comparar](evidencia/comparacion-vacio-1440.png) | [Comparar](evidencia/comparacion-vacio-1366.png) | [Comparar](evidencia/comparacion-vacio-390.png) |

Capturas individuales exigidas:

| Entregable | Captura |
| --- | --- |
| Mockup aprobado de Mis investigaciones | [1440 × 900](evidencia/mockup-investigaciones-1440.png) |
| Mis investigaciones en React | [1440 × 900](evidencia/react-investigaciones-1440.png) |
| Mockup aprobado del Asistente IA | [1440 × 900](evidencia/mockup-asistente-1440.png) |
| Asistente React con conversación persistida | [1440 × 900](evidencia/react-asistente-poblado-1440.png) |
| Asistente React sin materiales | [1440 × 900](evidencia/react-asistente-vacio-1440.png) |
| Asistente React móvil | [390 × 844](evidencia/react-asistente-poblado-390.png) |

También se entregan [consentimiento inicial](evidencia/consentimiento-antes-1440.png), [revocación](evidencia/consentimiento-revocado-1440.png), [fuentes](evidencia/react-fuentes-1440.png), [trazabilidad persistida](evidencia/react-trazabilidad-1440.png), [menú del proyecto](evidencia/react-menu-investigacion-1440.png), [confirmación de eliminación](evidencia/react-eliminar-investigacion-1440.png), [historial móvil](evidencia/react-historial-movil.png), [fuentes móviles](evidencia/react-fuentes-movil.png) y [navegación móvil](evidencia/react-navegacion-movil.png).

### Comparación de los diez puntos solicitados

| Punto | Resultado y diferencia explícita |
| --- | --- |
| 1. Navegación | 244 px en ambos escritorios, como el HTML; se conservan el fondo, los iconos, la investigación seleccionada y la jerarquía. En móvil se abre un cajón de 250 px con cierre interior y retorno del foco. |
| 2. Historial | Columna propia de 194 px entre navegación y conversación. El HTML no la incluye: se añade por la instrucción expresa de esta corrección. En móvil se abre desde Historial. |
| 3. Mensajes | Ancho máximo de lectura de 800 px, burbujas y avatares siguiendo la referencia. El espacio principal restante mide 1002 px en 1440 y 928 px en 1366; incluye sus márgenes interiores. |
| 4. Altura útil | Se elimina la altura fija del historial. La región desplazable de mensajes mide aproximadamente 618 px, 486 px y 533 px en los tres viewports, con permiso autorizado. La página del asistente ocupa exactamente el viewport, sin scroll vertical del documento. |
| 5. Escritura | Compositor al pie, de 800 × 62 px en escritorios y 362 × 62 px en móvil. Su borde inferior está en y=851, y=719 y y=793, respectivamente; permanece visible con historial largo. |
| 6. Fuentes y herramientas | Fuentes en panel plegable de 298 px, como el panel de materiales de referencia; en móvil aparece superpuesto. Los accesos llevan a las secciones reales. Las fuentes no forman una tarjeta permanente encima del chat. |
| 7. Tipografía | Familia system-ui y jerarquías de la referencia: bienvenida hasta 41 px; Asistente 27 px en escritorio y 18 px en móvil; metadatos y trazas en tamaño secundario. |
| 8. Densidad y espaciado | Listado con los mismos bloques de bienvenida, proporción 1.5:1, márgenes y filas. El chat ocupa su propio espacio, sin el encabezado académico ni una segunda tarjeta envolvente. El permiso autorizado añade una fila discreta al pie. |
| 9. Menús de proyectos | Tres puntos en cada fila, con Editar y Eliminar. El HTML original carece de estas acciones; se añaden por el alcance solicitado. Teclado, Escape, enfoque, cancelación y confirmación verificados. |
| 10. Consentimiento | Solicitud completa antes de autorizar, rechazo, ocultación tras aceptar, consulta y revocación. Reiniciar/F5 vuelve a solicitarlo. La demo declara procesamiento local y ausencia de Qwen3 real. |

Las mediciones completas están en [geometría con mensajes](geometria-poblado.json) y [geometría sin materiales](geometria-vacio.json). Los valores provienen de los elementos renderizados, no de suposiciones sobre las reglas CSS.

## B. Diferencias que permanecen frente al HTML

1. **Historial real:** columna adicional obligatoria de 194 px y Nueva conversación en ella. Desplaza el comienzo del área conversacional de x=244 a x=438 en escritorio. El ancho máximo del compositor y de lectura sigue siendo 800 px. En móvil, Historial ocupa el lugar del acceso directo a Nueva conversación del HTML; la creación sigue disponible dentro del historial y al enviar el primer mensaje autorizado.
2. **Estado real del proyecto:** la API de proyectos solo expone `draft`, presentado como Borrador. No se copian los recuentos de archivos ficticios del HTML ni se inventa un estado de avance. Los títulos, fechas, cantidad de proyectos y textos de respuestas corresponden a la base sintética de QA y pueden diferir de las referencias.
3. **CRUD real:** los tres puntos, formularios académicos completos y confirmaciones son controles reales ausentes en la maqueta de listado. El formulario conserva los campos obligatorios y las validaciones existentes. Al guardar o cancelar una edición iniciada en el listado, se regresa al listado.
4. **Consentimiento y trazas:** el HTML no implementa consentimiento real ni versiones de fuentes. Antes de autorizar hay una explicación completa junto al compositor. Después queda un indicador discreto con consulta y revocación, y las respuestas tienen detalles de fuentes/agentes plegables. Esos controles ocupan espacio adicional necesario respecto a la maqueta.
5. **Instrumento:** se conserva como funcionalidad pendiente. No se presenta una carga o extracción inexistente. El acceso secundario indica su estado y abre la pantalla correspondiente. No se inicia 18A.
6. **Información local:** el pie y la ayuda identifican el entorno sin autenticación y el uso de información ficticia. Las respuestas del proveedor simulado conservan su etiqueta. La aplicación no afirma que una respuesta histórica real fue simulada basándose solo en el proveedor actualmente seleccionado.
7. **Resto de pantallas:** no se intenta completar aquí su fidelidad integral. Reciben únicamente la navegación compartida y la retirada del CRUD del encabezado; se preservan los recorridos ya separados de Documentos, Metodología, Datos, Análisis, Resultados e Informes.

No se declara identidad píxel a píxel entre estados con distinto contenido ni aprobación del diseño por las pruebas. Las capturas permiten revisar estas diferencias; **la aceptación final corresponde a Melissa**.

## C. Verificación funcional y técnica

### Implementación

- `ResearchProjects` usa el proyecto de la fila como destino de eliminación; no cambia de proyecto ni entra al asistente para eliminarlo. Reutiliza `DeleteProjectDialog` y `ProjectService.delete`. Editar conserva la URL y el `ProjectForm` real. Los encabezados de secciones ya no contienen operaciones CRUD.
- `ActionMenu` proporciona menú contextual, flechas, Home/End, Escape, cierre al salir y retorno al disparador. No se sustituyen las confirmaciones del backend.
- `ConversationChat` se organiza en historial, conversación y contexto plegable. Conserva los servicios de listado, paginación, creación, selección, mensajes persistidos, recuperación tras error, eliminación e idempotencia. Una primera pregunta autorizada puede crear su conversación sin un paso previo obligatorio.
- Los mensajes usan el Markdown existente y soporte de tablas mediante [remark-gfm](https://github.com/remarkjs/remark-gfm). Se conserva el rechazo de HTML ejecutable, URLs inseguras e imágenes remotas en las respuestas. Las referencias técnicas permanecen en detalles desplegables.
- El consentimiento permanece exclusivamente en memoria del componente por proyecto. No se escribe autorización en localStorage ni sessionStorage. Solo se recuerda la conversación seleccionada. Cada POST de mensaje conserva `external_ai_consent: true` y `consent_scope: research_context_v2`, detrás del control explícito de autorización.

### Navegador contra API y SQLite reales de QA

Se verificó con datos exclusivamente ficticios:

- Crear proyecto, abrir el asistente, volver al listado, editar desde los tres puntos, guardar, recargar y recuperar la edición.
- Eliminar desde los tres puntos: cancelar y recuperar el foco; confirmar y comprobar su desaparición mediante el servicio real.
- Menú de proyecto con flechas y Escape. Ausencia de Editar/Eliminar investigación en Asistente y las otras seis secciones principales.
- Proyecto sin fuentes, conversación poblada, nueva conversación sin sobrescribir otra, selección de historial, eliminación de conversación con cancelación y confirmación.
- Rechazo de consentimiento, bloqueo de envío, autorización y ocultación, consulta y revocación, historial persistido y permiso desmarcado después de F5.
- Primer mensaje en un proyecto sin conversaciones: cero POST antes de autorizar; después, exactamente una creación y un envío, con consentimiento explícito. Ver [evidencia de primer mensaje](primer-mensaje.json).
- Navegación por URL, Atrás/Adelante y recarga de sección. Historial, fuentes y navegación global en móvil; cierre interior del cajón y restauración del foco.
- Estados reales de metodología, dataset, paquete y resultado en el contexto; detalles persistidos de fuentes y agentes de LangGraph. El proveedor de respuesta es simulado; la persistencia, composición de contexto y trazabilidad sí usan los servicios existentes.
- Documento sin desbordamiento horizontal en los tres tamaños y compositor visible. Listas, Markdown extenso, palabras largas, código y tabla de quince columnas verificados mediante una **fixture exclusiva del arnés de QA** que intercepta una lectura en el navegador. Esa fixture no se incorpora al frontend ni se guarda en la base. Las demás capturas y verificaciones usan respuestas reales de la API local. Ver [mediciones](markdown-stress.json) y [captura móvil de estrés](evidencia/react-markdown-stress-390.png).

Los registros de solicitudes sintéticas están en [chat/consentimiento](chat-navegador.json) y [CRUD/navegación](crud-navegador.json). No se realizaron inferencias externas. No se atribuye esta verificación a Qwen3 real.

### Pruebas y comprobaciones

| Comprobación | Resultado |
| --- | --- |
| Frontend Vitest completo | **150 pruebas aprobadas, 25 archivos**, con un worker en Windows e incluyendo diecinueve regresiones nuevas. Se adaptaron las pruebas existentes a los menús y detalles plegables, conservando las verificaciones de servicio, errores, permisos y persistencia. |
| Backend Conversation, contexto, proyectos, integración y contratos | **135 aprobadas** |
| Backend multiagente | **47 aprobadas**; total backend pertinente **182** |
| TypeScript | Aprobado con `tsc -b`, también incluido en el build principal |
| ESLint | Aprobado, cero advertencias |
| Prettier | Aprobado |
| Contratos backend y generación frontend | Aprobados, sin diferencias de contratos |
| Build principal y build Research independiente | Aprobados |
| Ruff y formato backend | Aprobados; 138 archivos Python conservan el formato |
| `git diff --check` | Aprobado |

Registros: [frontend](frontend-pruebas.log), [builds/lint/formato/contratos](frontend-comprobaciones.log), [backend](backend-pruebas.log), [multiagente](backend-multiagente.log).

Comandos principales:

```text
frontend: npm test -- --maxWorkers=1 --reporter=dot
frontend: npm run build
frontend: npm run build:research
frontend: npm run lint
frontend: npm run format:check
frontend: npm run contracts:generate
backend: python -m pytest tests/research/test_conversation.py tests/research/test_conversation_context.py tests/research/test_projects.py tests/research/test_application_integration.py tests/test_contracts.py -q
backend: python -m pytest tests/research/test_multiagent.py -q
backend: python -m scripts.export_contracts --check
backend: ruff check app tests
backend: ruff format --check app tests
```

Se resolvieron los fallos de adaptación de pruebas al mover acciones/plegar fuentes, una selección ambigua de botones y la espera del listado después de cancelar una edición. Dos corridas con dos workers registraron timeouts intermitentes de cinco segundos en pruebas de navegación. La ejecución final utilizó un worker; la configuración del repositorio permanece en dos. La comprobación conjunta de siete secciones se separó en casos independientes, conservando todas sus aserciones. No se ampliaron timeouts ni se eliminaron aserciones de seguridad. Se incorporaron además regresiones del envío durante la carga inicial y de eliminación tardía al navegar a otro proyecto o al proyecto eliminado. La revisión visual corrigió la jerarquía móvil del listado, alineación del encabezado/compositor, controles duplicados y el cierre del cajón cubierto por la navegación.

El build independiente informa un bundle de aproximadamente 525 kB, superior al umbral informativo de 500 kB; termina correctamente. La instalación mantiene el aviso existente de diez vulnerabilidades moderadas de npm; no se aplicaron actualizaciones forzadas ni se alteraron permisos. No hay un fallo funcional conocido pendiente en los recorridos comprobados. La inferencia real de Cloudflare/Qwen3 y la aprobación visual del usuario siguen fuera de esta validación.

## D. Estado Git y PR

- Repositorio: `Agape-exe/tesisstat-ai`.
- Worktree usado: `C:/Users/Melissa/Desktop/tesisstat-ai/redisenio-uxui-fase1`.
- Rama: `feat/redisenio-uxui-fase1`.
- HEAD y remoto del PR #57: `d6aebb280775983f9ee04dfae321dbb118b0986c`.
- Commits ya presentes: `d846444` y `d6aebb2`; **cero commits nuevos durante esta corrección**.
- Corrección y evidencia: cambios locales sin commit. La rama tiene cero commits de adelanto o retraso respecto a su remoto; el árbol contiene la corrección pendiente de revisión.
- `git fetch origin` al iniciar y al cerrar la comprobación remota. `origin/develop`: `9aa937ede037e3a7801557a87597632a05063947`; no hay commits remotos nuevos que integrar.
- [PR #57](https://github.com/Agape-exe/tesisstat-ai/pull/57): abierto, sin fusionar, todavía en `d6aebb2`. No se modificaron título, descripción, comentarios, checks ni estado del PR. La CI del PR no valida estos cambios locales sin publicar.
- [PR #53](https://github.com/Agape-exe/tesisstat-ai/pull/53): abierto en borrador, HEAD `f445957`, independiente y sin modificar ni integrar.
- Worktrees existentes preservados. Sin merge, rebase, reset, force push, cambios en `develop` ni publicación/despliegue.
- Sin cambios en backend, Statistics, LangGraph, contratos, cálculos, endpoints o permisos. No se inicia la Sesión 18A.

La siguiente decisión es la revisión visual del usuario. Esta entrega no autoriza ni realiza una publicación.
