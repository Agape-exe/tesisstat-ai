# Puente seguro de Research hacia Statistics

Los PR #12 y #13 ya están fusionados en develop. La sesión 13 conecta el puente
con el planificador y el motor reales para **resumen descriptivo y Pearson**, con
aprobación explícita, resultados persistidos y validación de vigencia.
El flujo, API, cálculos comprobados, pruebas y límites actuales están documentados
en [RESEARCH_STATISTICS_E2E.md](RESEARCH_STATISTICS_E2E.md).

`app.orchestration.research_statistics.ResearchStatisticsBridge` conserva su
responsabilidad: obtener el paquete vigente dentro del proyecto y resolver una
referencia opaca a bytes después de validar pertenencia, actividad, formato,
columnas, filas, tamaño y fuentes. Usa PackageReaderAdapter, PackageService y
DatasetService. No expone rutas privadas ni endpoints HTTP de bytes.

`backend/tests/research/test_statistics_bridge.py` sigue verificando ese límite
con CSV, XLSX, derivados, referencias incompatibles y fuentes obsoletas.
Estas pruebas por sí solas no son evidencia de ejecución estadística. Las pruebas
completas del planificador, aprobación y motor real sobre Research están en
`backend/tests/research/test_analysis_e2e.py`.

La demo es local, sin autenticación, exclusivamente para datos sintéticos.
Las demás técnicas de Statistics requieren adaptadores coordinados;
su implementación independiente no equivale a compatibilidad completa desde Research.
