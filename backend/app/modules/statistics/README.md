# Statistics Module — integrante 2

Entrada futura: ResearchPackage. Salidas futuras: AnalysisPlan y AnalysisResult. `ports.py`
separa planificación del motor determinista. Usar FixtureResearchReader para desarrollo
independiente. El motor solo ejecuta técnicas verificadas y aprobadas; no interpreta nombres de
técnicas como código.

## Descriptivos de demostración

`descriptive.py` implementa un motor puro y determinista para CSV sintéticos; `datasets.py`
limita la lectura a `association.csv` y `quality_issues.csv`; y `api.py` los presenta en una API
de desarrollo independiente. No modifica ni se monta desde `app.main`.

## Integración controlada con Research (ST-01)

`ports.py` expone `DatasetReader`, un puerto que recibe un `DatasetReference` y devuelve una
tabla validada. `research_bridge.py` adapta un lector de bytes inyectado por la composición de la
aplicación; Statistics no interpreta `location` como una ruta ni abre archivos arbitrarios.
`datasets.py` valida y parsea CSV UTF-8 y XLSX en memoria, comprueba límites, cabeceras,
dimensiones y la metadata de `DatasetReference`. `service.py` reutiliza el motor descriptivo
para columnas seleccionadas. La composición con `Research.DatasetService` queda fuera del
módulo hasta acordar el adaptador entre ambos integrantes.

- Una columna es **identificador** si su encabezado contiene un token `id`, `identifier`,
  `code`, `codigo` o `cod`; no se calcula como variable cuantitativa.
- Una columna es **numérica** únicamente si cada valor no faltante se puede convertir a un número
  finito. Los faltantes son cadena vacía, `NA`, `N/A`, `null` o `none` (sin distinguir mayúsculas).
  El resto es categórico.
- Media, mediana, mínimo, máximo, moda, varianza y desviación estándar se calculan solo con
  valores válidos. Varianza y desviación usan denominador muestral `n - 1`; para `n < 2` se
  devuelve ausencia con advertencia. Una columna constante tiene ambas métricas en cero.
- Los cuantiles p0, p25, p50, p75 y p100 siguen Hyndman–Fan tipo 7: interpolación lineal en
  `h = 1 + (n - 1)p`. No hay moda cuando todos los valores tienen frecuencia uno y se informan
  empates cuando varios valores comparten la frecuencia máxima.

Ejecutar la API de demostración desde `backend/`:

```powershell
uv run uvicorn app.modules.statistics.dev_app:app --reload --host 127.0.0.1 --port 8001
```

Rutas: `GET /datasets`, `GET /datasets/{dataset_id}/columns` y
`POST /datasets/{dataset_id}/descriptive` con `{"columns": ["study_hours"]}`.

## Comparaciones paramétricas (ST-05)

`comparisons.py` implementa t independiente con varianza combinada, t pareada y t de Welch con
grados de libertad de Welch–Satterthwaite. Se eliminan únicamente pares faltantes completos y
se rechazan muestras insuficientes o valores inválidos; las funciones devuelven estadísticas
reproducibles y todavía no realizan decisiones automáticas de significancia.

## Comparaciones no paramétricas (ST-06)

`nonparametric.py` implementa Mann–Whitney, Wilcoxon de rangos con signo y Kruskal–Wallis,
incluyendo rangos promedio para empates, eliminación explícita de diferencias cero y
validación de tamaños mínimos. Sus estadísticas se verifican con fixtures numéricos pequeños.

## Planner determinista (ST-02)

`catalog.py` contiene el catálogo declarativo de 18 técnicas inferenciales previstas y el
resumen descriptivo. `planner.py` implementa `DeterministicStatisticalPlanner`: consume un
`ResearchPackage` revisado, evalúa el tipo de hipótesis, roles, escalas y relación entre
observaciones, y devuelve un `AnalysisPlan`. Cuando la información es insuficiente devuelve
`needs_clarification` con preguntas explícitas; nunca inventa una técnica ni ejecuta cálculos.

## Motor determinista (ST-03)

`engine.py` implementa `DeterministicStatisticalEngine`. Exige planes `approved`, resuelve el
dataset mediante un mapa de referencias autorizado y, por ahora, ejecuta únicamente
`descriptive_summary`, devolviendo métricas, advertencias, comprobaciones y `AnalysisResult`.
Las técnicas catalogadas pero aún no implementadas terminan explícitamente en estado `failed`;
no se ejecuta código basado en nombres recibidos.

## Técnicas inferenciales iniciales (ST-04)

`inferential.py` implementa con la biblioteca estándar Pearson, Spearman, chi-cuadrado,
Fisher exacto para tablas 2×2 y alfa de Cronbach. Cada función valida tamaño, tipos, faltantes,
constantes y dimensiones, y devuelve métricas deterministas con pruebas de referencia. Estas
funciones todavía requieren un adaptador de columnas del `AnalysisPlan` para incorporarse al
motor de ejecución completo.

## ANOVA y comparaciones posteriores (ST-07)

`anova.py` implementa ANOVA de un factor, ANOVA de Welch, Tukey HSD y Games–Howell. Devuelve
estadísticos globales, grados de libertad y métricas por pares; deja explícito que la decisión
de significancia requiere el valor crítico de la distribución correspondiente.
