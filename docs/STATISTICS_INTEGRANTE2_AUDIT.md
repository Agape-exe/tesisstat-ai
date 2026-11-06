# Auditoría del plan de trabajo — Integrante 2

Actualizada contra `develop` después del merge del PR #50. Los avances de visualización de esta
rama quedan pendientes de su PR.

| Sesión | Estado | Evidencia / pendiente principal |
| --- | --- | --- |
| 15B — Validación del motor | En progreso | Pearson, Spearman, chi-cuadrado, t, ANOVA, Kruskal–Wallis, Mann–Whitney, Wilcoxon y los modelos de regresión/ANCOVA reportan p-valores con distribuciones deterministas. Kruskal–Wallis aplica corrección por empates y, cuando hay hasta 10 observaciones y como máximo 50 000 asignaciones, calcula un p-valor condicional exacto por permutación de rangos; fuera de ese límite declara la aproximación chi-cuadrado. Pruebas t, Pearson, Spearman y coeficientes de regresión/ANCOVA entregan IC 95 % cuando son estimables; el de Spearman se rotula como aproximación Fisher-z. Chi-cuadrado, ANOVA y no paramétricas incluyen medidas de magnitud. Tukey y Games–Howell informan p-valores por par y ajuste Bonferroni conservador, sin afirmar que sustituyen su distribución studentizada. Queda cobertura inferencial uniforme de técnicas que no disponen aún de distribución exacta. Se decidió no incorporar SciPy/statsmodels todavía: el motor mantiene implementaciones pequeñas, deterministas y sin dependencias científicas pesadas. |
| 16B — Técnicas fundamentales | Completada | Spearman, chi-cuadrado, Fisher, t independiente/pareada/Welch y ANOVA/ANOVA Welch recorren Research → propuesta → aprobación → ejecución. |
| 17B — Catálogo restante | Completada | Las 19 técnicas del catálogo tienen adaptadores de entrada, incluyendo Cronbach, no paramétricas, post-hoc, regresiones y ANCOVA. Los post-hoc conservan la advertencia de que la significancia requiere su distribución crítica. |
| 18B — Gráficos e interpretación | En progreso | La demo Statistics tiene histogramas, cajas, barras y dispersión para datasets de demostración. `ProjectAnalysis` visualiza métricas persistidas mediante un DTO interno: frecuencias categóricas, escalas de asociación/efecto acotado, intervalos de confianza, estimaciones divergentes, p-valores con alfa de referencia y registros válidos/faltantes. Para Pearson/Spearman puede solicitar explícitamente una dispersión de pares numéricos completos y para regresión/ANCOVA un diagnóstico de residuos frente a ajustados. Ambas rutas locales verifican resultado vigente, aprobado y completado, y vuelven a exigir la autorización ligada a paquete, dataset y versión para datos no sintéticos. Los contratos se acotan a 2 000 puntos y no exponen un endpoint genérico del dataset. Faltan gráficos específicos para otros modelos autorizados. |
| 19B — Informes académicos | En progreso | Las exportaciones TXT/DOCX/PDF incluyen metadatos reproducibles, contexto metodológico explícito y tablas numeradas de métricas y supuestos. Cuando existen métricas comparables, agregan una figura textual reproducible de asociaciones/efectos y p-valores con escala explícita y alfa solo como referencia. Para Pearson/Spearman suman una dispersión textual de pares autorizados y para regresión/ANCOVA un diagnóstico de residuos vs. ajustados con referencia cero; ambas se obtienen solo tras revalidar el resultado y autorización, sin una ruta genérica de datos. Falta revisión visual sistemática y figuras autorizadas para otros modelos. |
| 20B — Datos reales y pruebas integrales | Completada | Los datasets no sintéticos siguen denegados por defecto. La API y la vista local incorporan una autorización simulada, efímera y explícita, ligada a proyecto, paquete, dataset y versión de fuentes; se prueba acceso denegado, autorizado y revocado ante cambios. La matriz E2E documenta las 19 técnicas y el job Backend quality and tests ejecuta `uv run pytest` completo en Ubuntu para cada PR y push a `develop`, sin el límite temporal local. |

## Decisiones de seguridad y calidad

- No se modifican los contratos v1.0.0 sin una extensión versionada acordada.
- La autorización de datos se mantiene denegada por defecto hasta disponer de una política explícita.
- Las técnicas no emiten conclusiones automáticas cuando falta la distribución o condición necesaria para determinar significancia.
- Las referencias numéricas se cubren con fixtures pequeños y tolerancias; las dependencias científicas pesadas se reevaluarán solo si las implementaciones deterministas no cubren una distribución necesaria.

## Orden de continuación

1. Completar 15B: métricas inferenciales pendientes, intervalos de confianza y diagnósticos por técnica.
2. Completar 18B: contrato de datos gráficos y visualizaciones reales en `ProjectAnalysis`.
3. Completar 19B: informes DOCX/PDF con contexto metodológico, tablas y figuras.
4. Mantener 20B: preservar la autorización denegada por defecto y la cobertura E2E en CI.
