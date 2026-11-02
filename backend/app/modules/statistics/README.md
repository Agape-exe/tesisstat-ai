# Statistics Module — integrante 2

Entrada futura: ResearchPackage. Salidas futuras: AnalysisPlan y AnalysisResult. `ports.py`
separa planificación del motor determinista. Usar FixtureResearchReader para desarrollo
independiente. El motor solo ejecuta técnicas verificadas y aprobadas; no interpreta nombres de
técnicas como código.

## Descriptivos de demostración

`descriptive.py` implementa un motor puro y determinista para CSV sintéticos; `datasets.py`
limita la lectura a `association.csv` y `quality_issues.csv`; y `api.py` los presenta en una API
de desarrollo independiente. No modifica ni se monta desde `app.main`.

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
