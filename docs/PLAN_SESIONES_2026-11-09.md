# Plan acordado de sesiones — 9 de noviembre de 2026

Documento de contexto para chats independientes. Es una planificación, no evidencia de
funcionalidades terminadas. El código y los informes de cierre de cada sesión determinan
el estado real. Este acuerdo actualiza el orden del recorrido de la revisión del 8 de noviembre.

## Producto acordado

TesisStat AI ayuda a tesistas sin formación estadística a comprender sus datos, aclarar
lo necesario, revisar una propuesta, aprobarla y obtener resultados determinísticos explicados.
El participante 1 de la transcripción revisada es el docente.

Recorrido: contexto necesario → cargar datos → revisar datos → revisar propuesta →
aprobar y ejecutar → comprender resultados.

Crear proyecto pide únicamente nombre obligatorio y descripción opcional. Los datos
académicos existentes deben conservarse sin seguir bloqueando la creación. Se abre Inicio,
con avance y siguiente acción, en lugar del chat.

Navegación principal: Inicio, Contexto, Datos, Análisis y Resultados. El chat es ayuda
contextual desde el primer paso; formularios y botones permiten completar el recorrido
sin conversar. Instrumento es una ruta opcional para cuestionarios/escalas. Documentos de
apoyo son opcionales. Exportaciones e historial se presentan en Resultados.

Contexto inicial: título/nombre, pregunta u objetivo principal; objetivos específicos,
hipótesis y descripción del estudio cuando existan. Se completa progresivamente con
significado de variables, escalas, unidad observacional, dependencia entre mediciones
y muestreo cuando haga falta. No inventar hipótesis ni simular revisión metodológica.
Una ruta descriptiva no exige hipótesis. Se puede explorar datos con contexto incompleto.

Ingreso manual de contexto es obligatorio en alcance; prompt maestro e importación de una
respuesta estructurada son opcionales, siempre con previsualización y confirmación humana.
Conservar campos adicionales como contexto complementario; no interpretarlos automáticamente
como parámetros estadísticos. No se incluye un constructor ilimitado de campos.

## Base técnica revisada

Revisión inicial en develop, commit 955933bafabd4467ae08ab32b727bd6b8eda6a38. Antes de cada
sesión comprobar el estado actual; pueden haberse integrado cambios posteriores.

- React/TypeScript/Vite, FastAPI/Python 3.12, SQLite y almacenamiento local para la demo.
- Backend de desarrollo integrado: app.modules.research.dev_app:app, puerto 8001.
- Frontend local: puerto 5173.
- Carga CSV/XLSX, EDA, preparación, motor estadístico, planes, aprobación, historial y
  exportaciones ya existen y se reutilizan.
- La UI de Instrumento es un marcador de posición; su backend tiene extracción, revisión,
  reglas y mapeo. La previsualización de puntuaciones es interna, sin flujo público completo
  de confirmación/persistencia.
- El paquete y chat actuales dependen de metodología documental; contratos requieren hipótesis.
- El motor incluye 19 entradas de catálogo, contando descriptivos. La selección automática
  no cubre todo el catálogo: varias pruebas de integración sustituyen el planificador.
- Diagnóstico actual de normalidad: Jarque–Bera. Los post hoc nombrados Tukey/Games–Howell
  tienen aproximaciones documentadas que requieren corregirse o identificarse correctamente.
- Autenticación y persistencia de producción están pendientes. app.main no debe confundirse
  con la aplicación integrada de desarrollo.

La revisión ampliada está en REVISION_NECESIDADES_DOCENTE_2026-11-08.md. Contiene una propuesta
anterior de entrada por datos; para el orden de pantallas prevalece este plan y las decisiones
posteriores del usuario.

## Restricciones y forma de trabajar

- Plazo aproximado de cuatro días; priorizar un recorrido completo comprobable desde el día 2.
- Cada sesión se trabaja en un chat independiente y una rama codex/ específica, desde la
  base develop integrada correspondiente. No trabajar simultáneamente cambiando ramas en
  una misma copia: usar worktrees/copias separados para trabajo paralelo.
- Conservar cambios ajenos, históricos y datos existentes. Leer AGENTS.md si existe.
- No mostrar ni versionar .env, tokens, credenciales o datos personales. Usar ejemplos sintéticos.
- No realizar push, merge, publicar ni contratar servicios de pago sin instrucción explícita.
- Para dependencias entre sesiones, integrar primero la entrega anterior; no asumir que otra
  rama ya está disponible. No adaptar contratos centrales independientemente en dos chats.
- La IA propone/explica. Valores numéricos provienen del motor. Diagnósticos previos tienen
  una acción explícita; la inferencia final requiere un plan aprobado y vigente.
- Mantener trazabilidad, vigencia, revisión humana y versiones. Los cambios de contrato deben
  tener una estrategia de compatibilidad y pruebas; no desactivar validaciones para avanzar.
- No ampliar a clasificación, clustering, automatizaciones complejas ni rediseño visual total.
- Ejecutar verificaciones apropiadas al cambio y comprobar el flujo real afectado. Distinguir
  selección real de una técnica y ejecución de un plan forzado por tests.
- Actualizar README cuando cambien comandos y guardar un informe por sesión en
  docs/sesiones/SXX.md, o C01/C02 para tareas del compañero. Registrar rama, commit base,
  implementación, pruebas realmente ejecutadas, límites y siguiente dependencia.
- El informe usa los cinco campos pedidos: título, objetivo, modelo/esfuerzo declarado por el
  usuario, prompt/resumen de alcance y qué se logró. No afirmar el modelo de ejecución si
  no es verificable. No declarar completo un criterio pendiente.

## Secuencia y modelos recomendados

| ID | Entrega | Modelo / esfuerzo | Dependencias |
| --- | --- | --- | --- |
| S00 | Alcance, contratos y acuerdo de integración | GPT-6.1 Sol / Alto | Base actual |
| S01 | Creación simplificada, Inicio y navegación | GPT-6.1 Sol / Medio | S00 |
| S02 | Contexto editable y persistente | GPT-6.1 Sol / Alto | S00, S01 |
| S03 | Revisión guiada de datos y diccionario | GPT-6.1 Sol / Alto | S02 |
| S04 | Diagnósticos, recomendación y validación numérica | GPT-6 Astra / Alto | S03 |
| S05 | Instrumento opcional y puntuaciones | GPT-6.1 Sol / Alto | S04 |
| S06 | Tutor contextual y resultados unificados | GPT-6.1 Sol / Alto | S04, S05 |
| S07 | Revisión integral y correcciones de cierre | GPT-6 Astra / Alto | S06, C01 integrado |
| C01 | Autenticación y aislamiento por propietario | GPT-6.1 Sol / Alto | Contrato S00; ejecución paralela aislada |
| C02 | Ajustes visuales y accesibilidad acotados | GPT-6.1 Terra / Medio | Pantallas estabilizadas; opcional |
| S08 | Despliegue y verificación remota | GPT-6.1 Sol / Alto | S07 aprobado y autorización de despliegue |

S00 debe fijar técnicas y escenarios obligatorios para no comprometer todo el catálogo sin
validación; decisiones de identidad, propiedad y persistencia para producción; DTO/contexto
mínimo, versiones, endpoints y responsabilidades que desbloqueen las otras sesiones.
S00 entrega contratos y acuerdos, no implementa todos los módulos.

C01 no es únicamente una pantalla: backend valida identidad, impone propiedad en proyectos,
archivos, conversaciones y resultados, y aporta pruebas con dos usuarios. El modo local de
desarrollo debe quedar delimitado y no habilitar endpoints sin autenticación en producción.
Si faltan configuración o credenciales del proveedor, declararlo sin simular éxito.

S08 incluye persistencia durable y verificación de configuración, aislamiento, reinicio y
fuentes actuales. No basta publicar el frontend o ejecutar la app local sin autenticación.
Esta sesión se ejecutará después de terminar y revisar las funcionalidades.

## Distribución tentativa

Día 1: S00–S02; C01 puede comenzar después del acuerdo S00.
Día 2: S03–S04; al cierre debe existir un análisis completo con propuesta real.
Día 3: S05–S06 e integración de C01; C02 solo si hay margen.
Día 4: S07, correcciones y, tras aprobación, S08.

Es una distribución objetivo, no garantía de duración. Si una dependencia o una validación
falla, informar el alcance realmente logrado; no ocultar el pendiente para mantener el calendario.
