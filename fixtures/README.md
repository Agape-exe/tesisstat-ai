# Fixtures totalmente sintéticos

No hay personas, tesis ni resultados reales. Rutas relativas a la raíz del repositorio.

- `research/methodology.json`: proyecto, matriz e instrumento estructurados; sustituye los
  documentos de entrada mientras no exista extracción PDF/DOCX.
- `research/association.package.json`: salida metodológica compartida ya estructurada.
- `datasets/association.csv`: 30 registros reproducibles sin valores faltantes; solo pruebas
  de integración, no un estudio ni evidencia para recomendar una prueba determinada.
- `datasets/quality_issues.csv` y su `.expected.json`: duplicados, faltantes, valor no numérico
  y Likert fuera de rango para el futuro trabajo de preparación de datos.
- `statistics/association.plan.json` y `.result.json`: respuesta pendiente de aclaración y
  resultado sin ejecutar para que Research construya sus flujos sin un motor estadístico.

Uso independiente backend (desde `backend/`, ver `tests/test_module_boundaries.py`):

```python
from pathlib import Path
from app.shared.adapters.fixtures import FixtureResearchReader, FixtureAnalysisPlanner

root = Path.cwd().parent
research = FixtureResearchReader(root / "fixtures/research/association.package.json")
package = research.get_package("research-association")
planner = FixtureAnalysisPlanner(root / "fixtures/statistics/association.plan.json")
plan = planner.propose(package, "h1")
```

Frontend: importar JSON de fixtures y usar `createResearchMock` o `createStatisticsMock`
(ejemplo comprobable en `frontend/src/shared/mocks.test.ts`). No son endpoints públicos.
El mock del motor solo devuelve un fixture: **no ejecuta análisis**.
