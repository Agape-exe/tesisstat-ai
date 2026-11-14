# Auditoría del plan de trabajo — Integrante 2

Actualizada contra `develop` después del merge del PR #54. El cierre reúne los resultados de los
PR #51–#54: figuras autorizadas de asociación, residuos, grupos y pares, además de sus figuras
textuales reproducibles para informes.

| Sesión | Estado | Evidencia / pendiente principal |
| --- | --- | --- |
| 15B — Validación del motor | Completada | Pearson, Spearman, chi-cuadrado, t, ANOVA, Kruskal–Wallis, Mann–Whitney, Wilcoxon y los modelos de regresión/ANCOVA reportan p-valores con distribuciones deterministas. Kruskal–Wallis aplica corrección por empates y, cuando hay hasta 10 observaciones y como máximo 50 000 asignaciones, calcula un p-valor condicional exacto por permutación de rangos; fuera de ese límite declara la aproximación chi-cuadrado. Pruebas t, Pearson, Spearman y coeficientes de regresión/ANCOVA entregan IC 95 % cuando son estimables; el de Spearman se rotula como aproximación Fisher-z. Chi-cuadrado, ANOVA y no paramétricas incluyen medidas de magnitud. Tukey y Games–Howell informan p-valores por par y ajuste Bonferroni conservador, sin afirmar que sustituyen su distribución studentizada. Las técnicas que no cuentan con una distribución o condición suficiente conservan su advertencia y no emiten conclusiones automáticas. El motor se mantiene determinista y sin SciPy/statsmodels. |
| 16B — Técnicas fundamentales | Completada | Spearman, chi-cuadrado, Fisher, t independiente/pareada/Welch y ANOVA/ANOVA Welch recorren Research → propuesta → aprobación → ejecución. |
| 17B — Catálogo restante | Completada | Las 19 técnicas del catálogo tienen adaptadores de entrada, incluyendo Cronbach, no paramétricas, post-hoc, regresiones y ANCOVA. Los post-hoc conservan la advertencia de que la significancia requiere su distribución crítica. |
| 18B — Gráficos e interpretación | Completada | La demo Statistics tiene histogramas, cajas, barras y dispersión para datasets de demostración. `ProjectAnalysis` visualiza métricas persistidas mediante un DTO interno: frecuencias categóricas, escalas de asociación/efecto acotado, intervalos de confianza, estimaciones divergentes, p-valores con alfa de referencia y registros válidos/faltantes. Suma dispersión de pares completos para Pearson/Spearman, residuos frente a ajustados para regresión/ANCOVA, distribuciones por grupo para comparaciones independientes y cambios por pares para `t_paired`/Wilcoxon. Las rutas locales verifican resultado vigente, aprobado y completado, revalidan autorización ligada a paquete, dataset y versión para datos no sintéticos, y se acotan a 2 000 puntos con muestreo determinista, sin exponer un endpoint genérico del dataset. |
| 19B — Informes académicos | Completada | Las exportaciones TXT/DOCX/PDF incluyen metadatos reproducibles, contexto metodológico explícito y tablas numeradas de métricas y supuestos. Cuando existen métricas comparables, agregan figuras textuales reproducibles de asociación/efecto, dispersión de pares, residuos, distribución por grupo y cambios por pares, todas con escalas y advertencias explícitas. Cada figura se obtiene solo tras revalidar resultado y autorización, sin una ruta genérica de datos. La revisión visual y las limitaciones de codificación del PDF continúan documentadas como restricciones de la demo. |
| 20B — Datos reales y pruebas integrales | Completada | Los datasets no sintéticos siguen denegados por defecto. La API y la vista local incorporan una autorización simulada, efímera y explícita, ligada a proyecto, paquete, dataset y versión de fuentes; se prueba acceso denegado, autorizado y revocado ante cambios. La matriz E2E documenta las 19 técnicas y el job Backend quality and tests ejecuta `uv run pytest` completo en Ubuntu para cada PR y push a `develop`, sin el límite temporal local. |

## Decisiones de seguridad y calidad

- No se modifican los contratos v1.0.0 sin una extensión versionada acordada.
- La autorización de datos se mantiene denegada por defecto hasta disponer de una política explícita.
- Las técnicas no emiten conclusiones automáticas cuando falta la distribución o condición necesaria para determinar significancia.
- Las referencias numéricas se cubren con fixtures pequeños y tolerancias; las dependencias científicas pesadas se reevaluarán solo si las implementaciones deterministas no cubren una distribución necesaria.

## Validación de cierre

Desde `backend/`:

```powershell
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python -m scripts.export_contracts --check
uv run python -m compileall -q app scripts tests
```

Desde `frontend/`:

```powershell
npm ci
npm run lint
npm run format:check
npm test
npm run contracts:generate
npm run build
npm run build:research
```

CI repite estas validaciones en cada PR y en cada push a `develop`. Permanece pendiente solo el
merge manual de este cierre y, fuera del alcance de la demo local, autenticación, política de
autorización persistente, integración de datos reales y despliegue público.
