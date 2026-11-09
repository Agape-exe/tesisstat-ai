# Alcance definitivo y sesiones de TesisStat AI

Acuerdo normativo S00, 9 de noviembre de 2026. Describe trabajo por implementar;
no acredita funcionalidades nuevas. Base comprobada: `origin/develop`
`955933bafabd4467ae08ab32b727bd6b8eda6a38`, descargada durante S00.

Leer junto con [contratos](CONTRATOS_EVOLUCION.md), [integración](INTEGRACION_PARALELA.md)
y [evidencias de S00](sesiones/S00.md). Estos tres acuerdos rigen S01–S07.
README describe la demo vigente; PROJECT_CONTEXT y los informes anteriores son antecedentes.
Los documentos locales PLAN_SESIONES_2026-11-09 y REVISION_NECESIDADES_DOCENTE_2026-11-08
se consultaron, pero no se incorporan ni se modifican: no estaban versionados en la base.
Este acuerdo es autónomo respecto de ellos. Cambiar una decisión exige registrar motivo,
impacto y consumidores en el informe de la sesión responsable antes de implementar.

## Producto y límites

Asistente para tesistas sin formación especializada: contexto necesario → cargar datos →
revisar datos → revisar propuesta → aprobar y ejecutar → comprender resultados.
Crear solicita nombre obligatorio (provisional permitido) y descripción opcional; conserva
datos académicos anteriores. Abre Inicio con recorrido recomendado, avance y siguiente acción.
Navegación: Inicio, Contexto, Datos, Análisis, Resultados. Documentos son apoyo opcional de
Contexto; Instrumento es una ruta opcional desde Datos/Contexto; historial y exportaciones
pertenecen a Resultados. Conservar enlaces antiguos mediante alias.

Contexto manual, progresivo y editable: título; pregunta y objetivo principal; objetivos
específicos e hipótesis si existen; descripción del estudio y datos; variables, escalas,
unidad observacional, dependencia y muestreo cuando sean necesarios para la intención.
Explorar datos no exige contexto completo. Descriptivos no exigen hipótesis ni documento.
Chat disponible desde el inicio como ayuda contextual; formularios y botones completan todo
el recorrido. Una propuesta IA nunca confirma datos, aprueba planes ni reemplaza al motor.
Diagnósticos tienen acción explícita y alcance visible; la ejecución final exige aprobación.

Fuera: nuevas técnicas de clasificación/clustering, chat que automatice mutaciones complejas,
editor ilimitado de campos, rediseño visual completo y despliegue durante S00–S06.
Prompt maestro/importación estructurada y pulido visual son opcionales, con revisión humana.
No borrar técnicas existentes por quedar fuera de la validación prioritaria.

## Matriz verificable

O = obligatorio; P = opcional. «Existe» es inspección de código en la base, no QA de esta sesión.
Las rutas indicadas son relativas a la raíz del repositorio.

| Capacidad | Existe realmente / evidencia | Falta | Prioridad / sesión | Dependencia | Aceptación de salida |
| --- | --- | --- | --- | --- | --- |
| Crear proyecto | `research/projects/models.py`: título ≥5, universidad, programa y grado exigidos; CRUD SQLite | DTO mínimo, conservar académicos al editar | O / S01 | C1 | Crear con solo nombre no vacío; editar sin borrar académicos; recargar conserva datos |
| Inicio/navegación | `frontend/src/features/research/projects/navigation.ts`: 8 secciones; destino assistant | Inicio, 5 entradas y alias; avance derivado | O / S01 | C1 | Crear abre Inicio; siguiente acción y enlaces antiguos funcionan; móvil/teclado |
| Contexto manual | `research/methodology/models.py`: contenido y revisión vinculados a documento | Contexto autónomo, confirmación por campo, revisiones | O / S02 | C2 | Guardar/recargar sin documento; vacíos explícitos; propuesta IA no modifica confirmado |
| Entrada asistida adicional | Extracción documental y borradores existentes | Prompt maestro/importación con revisión | P / S02 o posterior | C2 | Vista previa, rechazo y confirmación; ningún valor inventado |
| Datos/perfil | `research/datasets/` CSV/XLSX; `research/eda/analyzer.py` faltantes, tipos, constantes, duplicados | Recorrido unido, diccionario humano y enlaces estables | O / S03 | C3 | CSV y hoja XLSX, códigos numéricos nominales, identificadores y faltantes; perfil sin contexto completo |
| Preparación | `research/preparation/models.py`: preview/hash/confirm y derivados | Unificar diccionario y trazabilidad tras renombrar/eliminar | O / S03 | C3 | Fuente intacta; derivado con receta/hash; vínculo eliminado obliga a revisar |
| Intención/paquete | `research/packages/use_cases.py` exige documento revisado, variables e hipótesis | Snapshot v2 por intención, sin hipótesis ficticia | O / S02 + S04 | C2–C4 | Descriptivo sin documento/hipótesis llega a propuesta real; históricos v1 legibles |
| Diagnósticos | `statistics/assumptions.py` calcula al ejecutar; normalidad JB desde n=8 | Acción previa persistida, casos efectivos y métodos válidos | O / S04a | C4, S03 | Diagnóstico acotado no ejecuta inferencia final; casos/grupos/pares y límites visibles |
| Recomendación | `statistics/planner.py` por hipótesis/escalas; comparación independiente pide aclaración; no recibe perfil | Decisión con intención/diseño/perfil; elección justificada y límites | O / S04b | S04a | Selección real sin sustituir planner; ambigüedad produce aclaraciones, no técnica arbitraria |
| Exactitud numérica | 19 técnicas en `statistics/engine.py`; cálculos propios, sin SciPy en pyproject | Referencias independientes, extremos, versión de motor | O / S04a–b | mínimo de técnicas | Estadístico/p/df/conteos coinciden con referencia y política declarada; ningún NaN/Infinity |
| Aprobación/vigencia | `orchestration/analysis_service.py`: token, snapshots, invalidación e históricos | Ruta v2 y revisiones no documentales; separar vigencia/ejecución | O / S04b | C4–C5 | Plan exacto aprobado; cambio de fuente bloquea ejecución/exportación sin borrar resultado |
| Instrumento | Backend extracción/revisión/mapeo; UI `ProjectInstrument.tsx` es placeholder | UI manual, contexto no documental; confirmación y puntuaciones durables | O cuando cuestionario / S05 | C6, S03–S04 | Ítems/opciones/inversión/reglas/mapeo revisados; score derivado y alfa con trazabilidad |
| Tutor | Conversaciones SQLite, LangGraph, consentimiento; `multiagent/tools.py` exige metodología/hipótesis | Contexto por etapa, mismo recomendador, propuestas revisables | O / S06 | C7, S02–S05 | Orienta desde Inicio sin documento; no fabrica números ni modifica por texto; flujo completo sin chat |
| Resultados | `analysis_models.py`, UI análisis, gráficos y reports TXT/DOCX/PDF | Presentación unificada, interpretación con referencias y límites | O / S06 | C5 | Tablas/gráficos/métricas/historial coherentes; exporta solo resultado vigente; histórico marcado |
| Identidad/propiedad | `shared/ports.py` anticipa IdentityProvider; SupabaseAdapter lanza NotImplementedError | Autenticación y aislamiento de todos los recursos | O antes de remoto / paralelo | acuerdo integración | Dos usuarios aislados, JWT inválido rechazado; producción falla cerrada |
| Persistencia durable | Repositorios SQLite y ficheros locales | Postgres/Storage, migración explícita y recuperación | O antes de remoto / paralelo + S07 | identidad + puertos | Reinicio conserva contexto, fuentes, planes, resultados, consentimientos; prueba recuperación |
| Cierre y remoto | Demo integrada solo en `research.dev_app`; `app.main` solo salud | Composition root autenticado y QA integral; despliegue posterior | O / S07; remoto posterior | todas las anteriores | Ningún endpoint de demo expuesto; funcionalidad y aislamiento comprobados antes de desplegar |

Prefijo backend abreviado en la tabla: `backend/app/modules/`, salvo `orchestration/` y
`shared/`, que parten de `backend/app/`. C1–C7 se definen en el acuerdo de contratos.

## Mínimo estadístico de cuatro días

La selección cubre orientación, datos tabulados, asociación, comparación y cuestionario
pedidos por el docente, reutilizando cálculos existentes. No promete terminar las 19 técnicas.
Mínimo obligatorio de validación: 9 técnicas: descriptive_summary, pearson, spearman,
t_welch, mann_whitney, t_paired, wilcoxon, t_independent y cronbach_alpha.
Welch será la propuesta habitual para dos medias independientes cuando proceda;
t independiente agrupada se conserva como alternativa con justificación explícita.
No elegir no paramétrica por «n menor que 50», ni usar p de normalidad como interruptor.

| Ruta | Selección que debe justificarse | Validación requerida |
| --- | --- | --- |
| Describir | Frecuencias/porcentajes para nominales/ordinales; resumen cuantitativo según escala; no promediar códigos | N total/válido/faltante, denominador visible, media/mediana/moda, DE/varianza muestral y cuantiles con convención explícita; constantes y n=0/1 |
| Asociar dos variables | Pearson: relación lineal cuantitativa, independencia y evaluación de influencia; Spearman: ordinal/monotonía, no aceptar mezcla nominal automáticamente | Casos completos conjuntos; coeficiente y p bilateral con método/limitaciones; empates, constantes, no linealidad y muestra insuficiente |
| Comparar dos grupos independientes | Confirmar unidad, independencia, agrupación con exactamente 2 niveles y resultado; Welch/Student o Mann–Whitney según pregunta y condiciones | Conteos por grupo, diferencia/media o efecto de rangos correctamente nombrado, estadístico/df/p; varianzas desiguales y tamaños dispares; Mann–Whitney no implica diferencia de medianas sin forma comparable |
| Comparar dos mediciones pareadas | Formato ancho: misma fila = mismo sujeto confirmado; dos columnas y dirección antes/después; t pareada o Wilcoxon con diferencias adecuadas | Pares completos, signo consistente, distribución de diferencias; ceros/empates; Wilcoxon y simetría; no tratar filas repetidas como independientes |
| Cuestionario | Constructo y agrupación de ítems confirmados; invertir antes de sumar/promediar; alfa en ítems recodificados, no en columna total | Al menos dos ítems, casos completos por regla, variación suficiente; inversión manual verificable, faltantes excluidos, alfa negativo permitido con advertencia; alfa no demuestra validez/unidimensionalidad |

Asociación categórica (chi_square/fisher_exact 2×2) es ampliación P de S04b: requiere
frecuencias esperadas y selector real, no solo prueba forzada. Más de dos grupos,
post hoc, ANCOVA y regresiones quedan fuera del mínimo prioritario, con capacidades e
históricos conservados. El recomendador nuevo debe señalar «fuera del alcance validado»
y ofrecer aclaración/alternativa pertinente; no forzar dos grupos ni una correlación.

Corrección obligatoria de exposición: los procedimientos actuales llamados Tukey y
Games–Howell son t/Welch por pares con Bonferroni (`statistics/anova.py`). S04 debe impedir
que nuevas propuestas/explicaciones los presenten como los procedimientos completos;
si no se implementan, etiquetar la aproximación y mantener históricos/versiones. No es
necesario implementar post hoc completos para cerrar el mínimo.

Decisión S04a: incorporar SciPy compatible con Python 3.12, fijada en lock tras medir
instalación/memoria, para diagnósticos y referencia numérica; conservar funciones puras y
adaptadores. No incorporar en bloque pandas/statsmodels/Pingouin sin necesidad concreta.
Usar Shapiro–Wilk para 3–5000 casos no constantes en la evaluación pertinente (por grupo o
diferencias); fuera de ese rango informar límites y evaluación gráfica, sin muestreo oculto
ni decisión automática. JB actual desde 8 no será la evidencia única para pequeñas muestras.
[SciPy Shapiro](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.shapiro.html)
documenta mínimo y límites de p; [JB](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.jarque_bera.html)
advierte su aproximación para muestras grandes. Métodos exactos/asintóticos y empates se
fijarán en S04a antes de generar fixtures, siguiendo
[Mann–Whitney](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html)
y [Wilcoxon](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html).
Estas referencias se consultaron el 9 de noviembre; aún no se ha instalado SciPy ni cambiado cálculos.

## Escenarios de aceptación integrados

Todos usan datos sintéticos, formularios y planner real. Los tests que sustituyen
`planner.propose` en `backend/tests/research/test_analysis_e2e.py` prueban adaptadores,
no acreditan selección automática. Conservarlos como regresión, añadir escenarios reales.

| ID | Preparación y acción | Resultado comprobable | Salida |
| --- | --- | --- | --- |
| E1 | Proyecto solo nombre; CSV de ventas ficticias; sin documento/hipótesis; elegir describir | Perfil accesible aun con contexto vacío; confirmar columnas; aprobar propuesta descriptiva, ejecutar, recargar y exportar | S04; UI final S06 |
| E2 | Dos cuantitativas lineales y dos ordinales con empates; confirmar intención/escalas | Pearson/Spearman justificados respectivamente; casos conjuntos; métricas de referencia, aprobación requerida | S04 |
| E3 | Grupo A/B y resultado cuantitativo heterocedástico; dataset ordinal alternativo | Welch/Mann–Whitney según condiciones; no bloqueo eterno en número de grupos ni técnica forzada | S04 |
| E4 | Antes/después por fila y un par faltante; alternativa con diferencias ordinales | Dependencia confirmada, t pareada/Wilcoxon según condiciones; exclusión conjunta; resultado conserva dirección | S04 |
| E5 | Tres ítems 1–5, uno inverso; regla suma y fila incompleta | Sin metodología documental; 1→5 y 5→1 verificables; derivado confirmado, fuente intacta; alfa sobre recodificados; revisión de mapeo | S05 |
| E6 | Columna constante, todos faltantes, grupo único, pares insuficientes, escala/unidad desconocida | Descriptivo limitado o needs_clarification/not_calculable con razón; no inferencia ni cifras IA; nunca NaN | S03–S04 |
| E7 | Aprobar; cambiar dataset, escala, dependencia, intención o regla pertinente | Plan/diagnóstico afectado stale; token viejo 409; resultado histórico legible; no ejecución/exportación vieja; nueva propuesta necesita aprobación | S04–S07 |
| E8 | Usuario A/B intenta ID/archivo/conversación/plan de otro; reinicio | 404 sin fuga, 401 con JWT inválido; datos propios permanecen; local sin dueño no se adopta al iniciar sesión | paralelo + S07 |
| E9 | Mismo caso por botones y con ayuda del tutor; proveedor ausente/cuota agotada | Mismo servicio de propuesta y controles; formularios siguen operativos; explicación enlaza métricas, no genera números | S06–S07 |

Validación numérica S04: guardar inputs sintéticos, versiones, opciones y valores de referencia
independientes del código de producción. Conteos exactos; tolerancia inicial estadístico/df
abs=1e-8, rel=1e-6; p abs=1e-8, rel=1e-5. Documentar excepciones por aproximación antes de
aceptarlas, sin relajar tolerancias para ocultar fallos. Comparar métodos equivalentes,
incluidos continuidad/empates/ceros y cuantiles. Si el motor usa SciPy, contrastar además
ejemplos manuales o referencias publicadas; invocar la misma función dos veces no valida exactitud.

## Plan ejecutable

Cada chat lee los tres acuerdos normativos y el informe previo integrado; verifica develop
y AGENTS si aparece; usa rama `<tipo>/<descripcion>` (por ejemplo, `docs/`, `feat/` o
`fix/`, según el trabajo) y deja informe SXX con pruebas reales y pendientes.
No asumir que una rama abierta ya está integrada. Modelo/esfuerzo son recomendaciones,
no afirmaciones sobre el modelo efectivo de un chat.

| Sesión / recomendación | Entradas necesarias | Entregables | Comprobaciones de salida |
| --- | --- | --- | --- |
| S00 / GPT-6.1 Sol, alto | Base real, decisiones del usuario y código | Estos acuerdos e informe; commits/PR | Referencias, ejemplos, estados, diff --check; solo documentación |
| S01 / GPT-6.1 Sol, medio | S00 C1 y alcance | DTO/proyecto mínimo, Inicio, 5 secciones y alias; informe | Solo nombre, edición preserva académicos, destino Inicio y navegación responsive; pruebas afectadas backend/frontend |
| S02 / GPT-6.1 Sol, alto | S01 integrado; C2/C4 estructura | Persistencia/contexto manual, intención, revisión/snapshots; adaptador documental explícito | Sin documento/hipótesis; unknown/null; concurrencia 409; borrador IA aislado; históricos v1 legibles |
| S03 / GPT-6.1 Sol, alto | S02; C3, fuentes/puertos | Datos integrado, diccionario, preparación confirmada y enlaces | CSV/XLSX, códigos/PII/faltantes, derivado/renombre, persistencia y fuente intacta |
| S04a / GPT-6 Astra, alto | S03; C4–C5 | Dependencia/lock SciPy justificados, diagnóstico explícito y validación del mínimo; límites de aproximaciones | Métodos/rangos/casos, referencias independientes, costes locales; no inferencia final por diagnóstico |
| S04b / GPT-6 Astra, alto | S04a; intención y snapshots v2 | Selector real, propuestas/aprobación/ejecución v2 y adaptación a cálculos puros | E1–E4/E6–E7, sin reemplazar planner; fixtures v1 y v2; ninguna hipótesis artificial |
| S05 / GPT-6.1 Sol, alto | S03–S04 y C6 | Instrumento opcional editable, mapeo/reglas, preview/confirm score, derivado durable y alfa | E5, límites/ceros/faltantes, stale por cambio, manual sin documento, alfa no equivale a validez |
| S06 / GPT-6.1 Sol, alto | S04/S05, C7 | Tutor por etapa, propuestas IA revisables, resultados/historial/exportaciones unificados | E9, consentimiento y redacción, proveedor ausente, cifras solo del motor, exportación vigente |
| S07 / GPT-6 Astra, alto | S01–S06 y entrega de identidad/persistencia integrada | QA integral y correcciones; composition root destino autenticado, checklist funcional final | E1–E9, dos usuarios, restart/recuperación; contratos y suites pertinentes; QA visual; límites declarados |

S04a/S04b subdividen S04 para separar exactitud de selección/integración; ambas obligatorias.
No cambiar numeración de las otras sesiones. Implementar v2 por capas: estructura C4 en
S02, perfil C3 en S03 y consumidores ejecutables C4/C5 en S04. Ninguna UI debe presentar
un adaptador aún pendiente como ejecutable.

Meta: día 1 S00–S02; día 2 S03–S04 y E1 más una asociación/comparación completa al cierre;
día 3 S05–S06 e integración paralela; día 4 S07/correcciones. El calendario no rebaja los
criterios. Despliegue se programa después de S07 funcional y validado (eventual S08,
fuera de estas implementaciones), con autorización propia y verificación remota posterior.
Los paquetes paralelos se delimitan en integración; su división detallada se decidirá después.
