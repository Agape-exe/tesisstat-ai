# Revisión del proyecto frente a las necesidades del docente

Fecha: 8 de noviembre de 2026.
Base revisada: `develop`, commit `955933bafabd4467ae08ab32b727bd6b8eda6a38`.
Fuente de requisitos: `Transcripcion_WhatsApp_07-11-2026.txt`; participante 1 = docente.

Este documento es una propuesta de adaptación basada en revisión de código, contratos,
pruebas existentes y documentación. No implementa funcionalidades ni acredita una validación
completa en navegador. Las intervenciones de los otros participantes no se tomaron como
requisitos del docente, y los ejemplos estadísticos de la conversación requieren revisión técnica.

## 1. Necesidad principal

El producto debe ayudar a una persona sin formación estadística a entregar sus datos,
comprender qué análisis puede hacer, aclarar lo indispensable, revisar una propuesta,
aprobarla y obtener cálculos reproducibles con una explicación comprensible.

Evidencias de la transcripción:

- 00:30–01:32: datos tabulados, descriptivos y resultados determinísticos; orientación sobre
  qué puede hacerse con el dataset.
- 02:03–03:29: el dataset es la entrada principal; apoyo en normalidad y pruebas de hipótesis.
- 03:29–04:40: tutoría para elegir pruebas según variables, cantidad de registros y distribución.
- 04:40–05:36: el usuario aprueba la propuesta antes de ejecutar; público no estadístico.
- 06:07: preguntas, hipótesis y objetivos pueden complementar los datos; no son una exigencia
  de subir una tesis completa.
- 07:24–07:56: el instrumento y su relación con los resultados importan y deben poder mostrarse.

Los comentarios sobre clasificación y clusterización ilustran amplitud de posibilidades;
no constituyen por sí solos un catálogo mínimo acordado. Conviene posponer esas familias
hasta cerrar un recorrido descriptivo e inferencial consistente.

## 2. Lo que existe y debe aprovecharse

| Capacidad | Evidencia en código | Lectura para la adaptación |
| --- | --- | --- |
| Carga y vista previa de CSV/XLSX | `backend/app/modules/research/datasets/`, `frontend/src/features/research/datasets/` | Base adecuada para comenzar por los datos. |
| Perfil exploratorio | `backend/app/modules/research/eda/analyzer.py` | Detecta faltantes, duplicados, constantes, posibles identificadores, tipos sugeridos y problemas de calidad. No equivale a una escala de medición confirmada. |
| Preparación con derivados | `backend/app/modules/research/preparation/` | Reutilizar sin modificar silenciosamente la fuente. |
| Estadística descriptiva | `backend/app/modules/statistics/descriptive.py` | Ya incluye media, mediana, moda, varianza muestral, desviación y cuantiles. |
| Técnicas inferenciales y regresión | `backend/app/modules/statistics/catalog.py`, motores asociados | Catálogo de 19 entradas: 18 técnicas adicionales al resumen descriptivo. Disponibilidad del motor y recomendación automática son capacidades distintas. |
| Propuesta, aprobación, ejecución e historial | `backend/app/orchestration/analysis_service.py`, repositorio y rutas | Mantener la aprobación ligada a la versión exacta del plan y de sus fuentes. |
| Tablas, gráficos e informes | `frontend/src/features/research/analysis/`, `backend/app/modules/statistics/reports.py` | Presentar como salida del análisis, accesible también sin tesis completa. |
| Conversación con fuentes verificadas | `backend/app/modules/conversation/research_context.py`, `backend/app/orchestration/multiagent/` | Reutilizar para explicar evidencia y solicitar aclaraciones. |
| Instrumentos, extracción y mapeo | `backend/app/modules/research/instrument/`, rutas montadas en `dev_app.py` | Backend avanzado que aún necesita interfaz funcional. |
| Puntuaciones e inversión de ítems | `backend/app/modules/statistics/scoring.py`, `backend/app/orchestration/instrument_scoring_preview.py` | Hay cálculo y previsualización interna; no hay todavía un recorrido público completo de confirmación y persistencia de puntuaciones. |

## 3. Brechas verificadas

### 3.1 El documento metodológico bloquea el análisis principal

`backend/app/modules/research/packages/use_cases.py`, método `validate`, exige seleccionar
un documento metodológico, confirmar su revisión, disponer de título y variables, y vincular
hipótesis explícitas con objetivos revisados. Esto impide el recorrido principal con solo un CSV.

Además, `ResearchPackage` exige hipótesis y `AnalysisPlan` exige `hypothesis_id` en
`backend/app/shared/contracts.py`. No basta ocultar pantallas o quitar validaciones de interfaz.

Propuesta: incorporar un contexto de análisis originado en el dataset, con intención analítica
y confirmaciones mínimas. El origen documental será una ampliación opcional. Decidir entre
un contrato nuevo y una evolución compatible después de revisar los consumidores; conservar
la lectura de históricos. No inventar hipótesis ni marcar metodología como revisada para
satisfacer artificialmente el contrato actual.

### 3.2 El planificador no evalúa los datos para seleccionar todas las alternativas

`backend/app/modules/statistics/planner.py` recibe un paquete y una hipótesis. Selecciona
principalmente por tipo de hipótesis, escalas, roles y dependencia declarada; no recibe un
perfil con distribuciones, faltantes efectivos, tamaños por grupo o resultados diagnósticos.

Ejemplos verificables:

- Dos escalas cuantitativas en asociación conducen a Pearson sin evaluar antes linealidad
  o valores influyentes.
- La comparación independiente devuelve una aclaración sobre la cantidad de grupos.
- No existe selección automática completa de Fisher, Welch, ANOVA o sus alternativas a
  partir de observaciones y diagnósticos del dataset.

La integración puede ejecutar estas técnicas cuando recibe un plan compatible. Sin embargo,
varias pruebas de `backend/tests/research/test_analysis_e2e.py` sustituyen `planner.propose`
para forzar Fisher, t independiente, Welch, Mann–Whitney, alfa, multigrupo y post hoc.
Esas pruebas acreditan el recorrido de ejecución de una propuesta suministrada, no la selección
automática de la técnica por el planificador real.

### 3.3 La pantalla de instrumento aún es un marcador de posición

`frontend/src/features/research/instrument/ProjectInstrument.tsx` muestra
«Instrumento: próximamente». Falta conectar extracción, revisión de ítems y escalas,
confirmaciones, reglas y mapeo de ítems a columnas ya disponibles en el backend.

El flujo de instrumento también tiene vinculaciones metodológicas actuales que deberán
revisarse para permitir un contexto mínimo confirmado sin tesis completa. No basta conectar
la interfaz y conservar todas las dependencias obligatorias existentes.

### 3.4 La orientación del chat también depende de metodología y paquete

`VerifiedPlanningReader.inspect` en `backend/app/orchestration/multiagent/tools.py` exige
una única metodología confirmada, paquete vigente y una hipótesis identificable. El chat no
resuelve todavía «cargué estos datos, ¿qué puedo hacer?» como recorrido completo.

El enrutador bloquea solicitudes de cálculo/aprobación/ejecución por texto. Puede conservarse
la ejecución mediante controles explícitos, pero el asistente debe conducir a propuestas y
acciones concretas usando el mismo servicio de planificación que la interfaz.

### 3.5 Determinismo y validez estadística deben verificarse por separado

- `assumptions.py` usa Jarque–Bera desde ocho valores, con aproximación asintótica. No hay
  Shapiro–Wilk. SciPy advierte que la aproximación de Jarque–Bera requiere muestras grandes
  (>2000), por lo que no debe ser el diagnóstico único para muestras pequeñas de tesis.
- `anova.py` devuelve comparaciones por pares t/Welch con ajuste Bonferroni bajo nombres
  Tukey/Games–Howell, y lo advierte. Esos resultados no deben presentarse como una
  implementación completa de los procedimientos nombrados.
- Los supuestos se calculan en el motor durante la ejecución; falta una etapa diagnóstica
  que fundamente la propuesta antes de aprobar la inferencia final.
- El proyecto declara bibliotecas estadísticas especializadas como dirección futura, pero
  `backend/pyproject.toml` todavía no incluye SciPy, NumPy o statsmodels.

Propuesta: validar los cálculos frente a implementaciones de referencia, corregir o renombrar
las aproximaciones y versionar el motor cuando cambien los resultados. Considerar bibliotecas
estadísticas mantenidas tras revisar compatibilidad y recursos, sin reescribir todo el sistema.

## 4. Recorrido recomendado

1. Crear un análisis con nombre e importar CSV/XLSX. Los datos universitarios del proyecto
   pueden quedar como información opcional: hoy universidad, programa y grado son obligatorios.
2. Obtener un perfil determinista con filas, columnas, casos válidos, faltantes, grupos,
   identificadores probables y problemas de calidad.
3. Mostrar un diccionario editable: significado de cada columna, tipo de almacenamiento,
   escala confirmada y rol en el análisis. Un número puede ser un código nominal o un ítem ordinal.
4. Ofrecer rutas comprensibles: describir, relacionar, comparar, evaluar consistencia interna
   de un cuestionario o predecir una variable cuantitativa.
5. Preguntar únicamente lo necesario: qué representa cada fila, objetivo, columnas de interés,
   grupos independientes o mediciones de las mismas personas. Si se necesita inferencia
   poblacional, pedir también el contexto de muestreo relevante.
6. Permitir una evaluación diagnóstica explícita. Distinguir su autorización de la aprobación
   del análisis final y conservar qué se calculó y con qué fuentes.
7. Presentar alternativas y una propuesta justificada: pregunta que responde, variables,
   casos utilizables, supuestos, evidencia, pendientes y límites.
8. El usuario confirma las aclaraciones y aprueba un plan determinado.
9. Ejecutar mediante el motor permitido, persistir métricas y explicar los resultados con
   referencias a esas métricas. La IA no aporta números que no existan en la salida del motor.
10. Exportar resultados y conservar historial. Si cambian datos, escalas o diseño, invalidar
    la propuesta anterior sin borrar el resultado histórico.

El instrumento es una ruta adicional cuando hay cuestionario o escala. Un reporte de ventas
debe poder analizarse sin inventar dimensiones, ítems o un instrumento psicométrico.

Con el dataset solo se pueden sugerir posibilidades y evaluar condiciones observables. La
independencia, el diseño, la representatividad y el objetivo no pueden deducirse con certeza
de los tipos de columnas. Es correcto pedir aclaraciones o limitarse a descriptivos.

## 5. Precisión sobre los ejemplos del docente

Preservar la necesidad expresada, sin convertir ejemplos tentativos en reglas del software:

- No establecer «menos/más de 50 = Wilcoxon u otra prueba». Distinguir grupos independientes
  y datos pareados; el tamaño y los empates influyen también en el método de cálculo del p-valor.
- No establecer «Shapiro no significativo = prueba paramétrica autorizada». Es una evidencia
  parcial; debe evaluarse junto con diseño y supuestos de la técnica.
- En una comparación pareada importa la distribución de las diferencias; en modelos, los
  supuestos correspondientes a residuos. La normalidad de cualquier columna aislada no basta.
- Un resultado no significativo de normalidad no demuestra normalidad.
- Separar preguntas confirmatorias de exploración para no producir automáticamente pruebas
  de todas las combinaciones y luego destacar únicamente las significativas.

Fuentes primarias consultadas:

- [SciPy: Shapiro–Wilk](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.shapiro.html).
- [SciPy: Jarque–Bera](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.jarque_bera.html).
- [SciPy: Mann–Whitney](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html).
- [SciPy: Wilcoxon](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html).

## 6. Paquetes de trabajo para futuros prompts

Orden sugerido; son alcances propuestos, no instrucciones de ejecución en este documento.

| Orden | Entrega | Criterio de aceptación principal |
| --- | --- | --- |
| 1 | Contexto mínimo y contratos para comenzar por datos | Un CSV permite perfil y propuesta descriptiva sin documento, hipótesis ficticia ni revisión metodológica simulada; históricos siguen legibles. |
| 2 | Interfaz guiada desde Datos | El usuario carga, confirma significado/escalas, elige una intención y entiende qué falta. Documentos y cuestionario son opcionales según el caso. |
| 3 | Diagnósticos y revisión del motor numérico | Normalidad y otras condiciones tienen método, alcance y límites explícitos; resultados de técnicas prioritarias coinciden con referencias y aproximaciones están correctamente nombradas. |
| 4 | Recomendador basado en evidencia | Perfil + intención + contexto confirmado producen opciones justificadas; comparación independiente y Fisher se prueban sin sustituir el planificador. |
| 5 | Instrumento visible y puntuaciones | La interfaz permite revisar y mapear ítems; la puntuación confirmada se conserva con trazabilidad y se puede usar en análisis posteriores. |
| 6 | Tutor conversacional conectado | «¿Qué puedo hacer con estos datos?» muestra opciones reales y conduce a la propuesta; cambiar de canal no cambia las reglas ni evade aprobaciones. |
| 7 | Demostración integral e informes | Recorridos completos con datos de ventas, cuestionario y pre/post, más casos con faltantes, constantes o contexto insuficiente; sin documentos obligatorios ni planificador sustituido. |

Cada prompt debe especificar la base actual de `develop`, una rama `codex/`, archivos y contratos
que consumirá, alcance limitado, criterios verificables, tratamiento de históricos y pruebas de
regresión del recorrido existente. Evitar que dos chats cambien contratos centrales sin coordinar.
Estos paquetes tienen dependencias; no deben iniciarse todos a la vez.

Para una primera demostración al docente: CSV → perfil → pregunta sencilla → descriptivos →
una asociación o comparación bien fundamentada → aprobación → resultado e informe.
Luego añadir el cuestionario completo. Posponer clasificación, clustering y despliegue público
como nuevas prioridades hasta cerrar ese recorrido.

## 7. Alcance de la revisión y estado del entorno

- Se descargó `origin/develop` y se creó la rama local `develop` con seguimiento remoto;
  HEAD y `origin/develop` coinciden en el commit indicado. La descarga no pidió iniciar sesión.
- La identidad local de Git de este repositorio quedó como Melissa Yengle,
  `melissayengle@gmail.com`. Esto configura autoría de commits, no autentica una cuenta GitHub.
- No se modificó código funcional, no se crearon commits, no hubo push ni PR.
- Se ejecutaron directamente las cuatro comprobaciones existentes de
  `backend/tests/test_assumptions.py`: pasaron. Son comprobaciones parciales con Python 3.14,
  no una validación del entorno soportado ni de exactitud de todas las técnicas.
- El proyecto requiere Python 3.12 y uv. En el entorno revisado no hay uv, `.venv`, dependencias
  de backend ni `frontend/node_modules`; Python disponible es 3.14. Node es 24.13.0.
- No se ejecutaron la suite completa, compilaciones ni un recorrido de navegador. Los registros
  de QA previos del repositorio son antecedentes y no se presentan como pruebas de esta revisión.

Conclusión: la base técnica es reutilizable. El cambio central es permitir que el contexto
analítico nazca de los datos y que la tutoría guíe la selección de pruebas con evidencia,
manteniendo la aprobación humana, los cálculos deterministas y la trazabilidad.
