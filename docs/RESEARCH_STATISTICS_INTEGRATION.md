# Puente seguro de Research hacia Statistics

Los PR #12, #13 y #14 ya están fusionados en develop. La sesión 13 conserva el
helper `build_engine_from_research_bridge` del Integrante 2 y completa el flujo
para **resumen descriptivo, Pearson, Spearman, comparaciones de dos grupos y
comparaciones multigrupo** con aprobación independiente, resultados persistidos y
vigencia. Ver [RESEARCH_STATISTICS_E2E.md](RESEARCH_STATISTICS_E2E.md).

`ResearchStatisticsBridge` valida proyecto, paquete, referencia opaca, dataset
activo, formato, columnas, filas, tamaño y fuentes antes de proporcionar bytes.
Statistics nunca recibe rutas privadas y no hay endpoints de descarga de bytes.

Las rutas `/statistics` incorporadas por el PR #14 ahora delegan en el mismo
servicio persistido que `/analysis`. `approve=true` en una ejecución no aprueba
un plan nuevo ni uno que requiera aclaraciones: se exige un `plan_id` persistido
con aprobación previa mediante `/analysis/plans/{plan_id}/approve`.
El panel `ResearchStatisticsPanel` del compañero se conserva sin modificaciones;
no se monta en la demo Research porque usa el protocolo anterior. La demo usa
`ProjectAnalysis`, con las acciones y advertencias completas.

Las pruebas originales del puente verifican lectura autorizada. Las pruebas de
runtime verifican compatibilidad y rechazo del atajo de aprobación. El recorrido
completo está en `backend/tests/research/test_analysis_e2e.py`, con documentos y
archivos realmente almacenados por Research, planificador y motor existentes.

La demo es local y solo para datos sintéticos. El flujo Research→Statistics conecta
las 19 técnicas del catálogo, incluyendo Tukey HSD, Games–Howell, ANCOVA y regresión
lineal simple y múltiple. La integración no cambia los seis contratos ni las fórmulas
del módulo Statistics.
