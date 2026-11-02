# Auditoría del plan de trabajo — Integrante 2

Actualizada contra `develop` después del merge del PR #34.

| Sesión | Estado | Evidencia / pendiente principal |
| --- | --- | --- |
| 15B — Validación del motor | En progreso | Pearson, Spearman, chi-cuadrado, t, ANOVA, Kruskal–Wallis, Mann–Whitney, Wilcoxon y los modelos de regresión/ANCOVA reportan p-valores con distribuciones deterministas; Kruskal–Wallis aplica corrección por empates. Pruebas t, Pearson y coeficientes de regresión/ANCOVA entregan IC 95 % cuando son estimables; chi-cuadrado, ANOVA y no paramétricas incluyen medidas de magnitud. Quedan IC para Spearman y cobertura inferencial uniforme de técnicas que no disponen aún de distribución exacta. Se decidió no incorporar SciPy/statsmodels todavía: el motor mantiene implementaciones pequeñas, deterministas y sin dependencias científicas pesadas. |
| 16B — Técnicas fundamentales | Completada | Spearman, chi-cuadrado, Fisher, t independiente/pareada/Welch y ANOVA/ANOVA Welch recorren Research → propuesta → aprobación → ejecución. |
| 17B — Catálogo restante | Completada | Las 19 técnicas del catálogo tienen adaptadores de entrada, incluyendo Cronbach, no paramétricas, post-hoc, regresiones y ANCOVA. Los post-hoc conservan la advertencia de que la significancia requiere su distribución crítica. |
| 18B — Gráficos e interpretación | Parcial | La demo Statistics tiene histogramas, cajas, barras y dispersión para datasets de demostración. `ProjectAnalysis` ahora visualiza métricas persistidas: barras de frecuencias categóricas, escalas de asociación/efecto acotado e intervalos de confianza. Faltan gráficos que requieran observaciones crudas (por ejemplo, dispersión o residuos) y contexto interpretativo más rico. |
| 19B — Informes académicos | Parcial | Las exportaciones TXT/DOCX/PDF incluyen metadatos reproducibles, contexto metodológico explícito y tablas numeradas de métricas y supuestos. Faltan figuras derivadas de datos reales y revisión visual sistemática. |
| 20B — Datos reales y pruebas integrales | Pendiente | El servicio integrado sigue denegando datasets no sintéticos por defecto. Falta una interfaz de autorización simulada, pruebas de acceso autorizado/no autorizado y E2E válido para las 19 técnicas. |

## Decisiones de seguridad y calidad

- No se modifican los contratos v1.0.0 sin una extensión versionada acordada.
- La autorización de datos se mantiene denegada por defecto hasta disponer de una política explícita.
- Las técnicas no emiten conclusiones automáticas cuando falta la distribución o condición necesaria para determinar significancia.
- Las referencias numéricas se cubren con fixtures pequeños y tolerancias; las dependencias científicas pesadas se reevaluarán solo si las implementaciones deterministas no cubren una distribución necesaria.

## Orden de continuación

1. Completar 15B: métricas inferenciales pendientes, intervalos de confianza y diagnósticos por técnica.
2. Completar 18B: contrato de datos gráficos y visualizaciones reales en `ProjectAnalysis`.
3. Completar 19B: informes DOCX/PDF con contexto metodológico, tablas y figuras.
4. Completar 20B: puerto de autorización simulada para datos reales y matriz E2E completa.
