# feat(research): implementar InstrumentContext v1.0.0, persistencia SQLite versionada, API FastAPI y puerto para Statistics (Sesiones 18A-1, 18A-2, 18A-3)

## Resumen Ejecutivo

Esta entrega consolida el trabajo backend de las **Sesiones 18A-1, 18A-2 y 18A-3**, estableciendo el contrato canónico independiente `InstrumentContext v1.0.0` para instrumentos de investigación psicométricos, su persistencia SQLite inmutable y versionada con concurrencia optimista, su API REST completa en el entorno de desarrollo y el adaptador de lectura desacoplado para el módulo de Statistics (preparando la futura Sesión 22B).

**Nota de alcance:** Esta entrega es 100 % de dominio, persistencia, servicios y API backend. La extracción documental (PDF/DOCX) y la interfaz de usuario en React se desarrollarán en entregas posteriores.

---

## 1. Contrato Canónico `InstrumentContext v1.0.0` (18A-1)

Estructura acordada y formalmente ratificada entre Research (Integrante 1) y Statistics (Integrante 2) con los cinco ajustes definitivos:
1. `methodology_review_id`: Emplea el UUID `document_id` de la revisión metodológica confirmada, validando versión y hash SHA-256.
2. `dataset_version`: Se elimina formalmente de `dataset_mapping`. La vigencia del dataset se valida mediante `dataset_id` (UUID) y `dataset_hash` (SHA-256 hex digest).
3. `reverse_rule`: Admite exclusivamente la constante `"min_plus_max_minus_value"`.
4. Estados del instrumento: Admite exclusivamente `"draft"`, `"reviewed"` y `"stale"`.
5. Estados del mapeo: Admite exclusivamente `"draft"`, `"confirmed"` y `"stale"`.

### Características de Integridad
- **Confirmación Humana Explícita:** Representada por `InstrumentConfirmation(state="pending" | "confirmed", confirmed_at=..., confirmer_ref=...)`.
- **Identificadores Públicos:** `item_id` y `scoring_rule_id` identifican entidades unívocamente.
- **Opciones de Respuesta Cuantitativas:** `code: str`, `label: str`, `numeric_value: float`.
- **Reglas de Puntuación Declarativas:** Con `scope` (`"dimension"` o `"instrument"`), agregación (`"sum"` o `"mean"`), política de faltantes (`"all_required"`) y estado de confirmación.
- **Protección contra Fugas y PII:** DTOs con `extra="forbid"` y rechazo estricto de columnas que representen datos personales en el mapeo de datasets.

---

## 2. Persistencia SQLite y Concurrencia Optimista (18A-2)

- **Tabla `research_instruments`:** Clave primaria compuesta `(id, version)` e índice parcial único `(project_id, id) WHERE is_current = 1`.
- **Integridad Referencial:** Declaración formal `FOREIGN KEY (project_id) REFERENCES research_projects(id) ON DELETE CASCADE` con `PRAGMA foreign_keys = ON` activado por conexión y trigger de cascada para compatibilidad.
- **Concurrencia Optimista:** Transacciones `BEGIN IMMEDIATE` y exigencia de `expected_version` en todas las mutaciones. Modificaciones desincronizadas levantan `InstrumentConflict` (HTTP 409).
- **Inmutabilidad del Historial:** Las versiones anteriores permanecen archivadas con `is_current = 0`, accesibles cronológicamente mediante `get_history()` o consultas por versión.
- **Detección Dinámica de Obsolescencia (`check_stale`):** Verifica en tiempo real si la revisión metodológica o el archivo del dataset mutaron alterando sus hashes SHA-256.

---

## 3. API REST FastAPI (18A-3 y Ajustes de Integridad)

Montada bajo el prefijo unificado `/api/research/projects/{project_id}/instruments` en `backend/app/modules/research/dev_app.py`:
- `POST /` — Crea borrador inicial $v0$ (HTTP 201 + Header `Location`).
- `GET /` — Lista instrumentos del proyecto (HTTP 200).
- `GET /{instrument_id}` — Consulta el instrumento activo o versión histórica mediante `?version=N` (HTTP 200).
- `PUT /{instrument_id}` — Actualiza borrador con control optimista `expected_version` e invalidación automática de mapeos si hubo cambios estructurales (HTTP 200).
- `POST /{instrument_id}/methodology` — Vincula revisión metodológica confirmada validando correspondencia estricta de variables (`variable_links`) (HTTP 200).
- `POST /{instrument_id}/rules/confirm` — Confirma explícitamente reglas de puntuación específicas o todas (HTTP 200).
- `POST /{instrument_id}/confirm` — Confirmación humana explícita tras verificar que todas las reglas estén previamente confirmadas (HTTP 200).
- `POST /{instrument_id}/mark-stale` — Materializa explícitamente y de forma transaccional la obsolescencia respecto a fuentes (HTTP 200).
- `POST /{instrument_id}/mapping` — Asocia columnas de dataset sin PII (HTTP 200).
- `POST /{instrument_id}/mapping/confirm` — Confirma el mapeo tras validar cobertura al 100 % (HTTP 200).
- `GET /{instrument_id}/history` — Retorna el historial de versiones (HTTP 200).

Mapeo de errores coherente: HTTP 200, 201, 404, 409, 422 y 503 sin divulgar detalles internos ni retornar 500 para errores de dominio controlados.

---

## 4. Adaptador de Lectura para Statistics

- **Puerto:** `InstrumentContextReader(Protocol)` en `backend/app/modules/research/ports.py`.
- **Implementación:** `ResearchInstrumentContextReader` en `backend/app/modules/research/instrument/reader.py`.
- **Garantías de Soberanía:** Statistics nunca accede a tablas ni repositorios de Research; solo consume el puerto de solo lectura. El lector rechaza instrumentos en estado borrador, pendientes de confirmación o desactualizados (`stale`).
- **Contratos Compartidos:** `ResearchPackage v1.0.0` y `backend/app/shared/contracts.py` no sufrieron alteración alguna.
- **Módulo Statistics:** Ningún archivo de `backend/app/modules/statistics/` fue modificado.

---

## 5. Artefactos y Esquemas Exportados

Se incluyen en `docs/contracts/`:
- `docs/contracts/instrument_context_v1.schema.json`: Esquema JSON estándar (Draft 2020-12) reproducible y compartible.
- `docs/contracts/examples/instrument_confirmed_with_mapping.json`: Ejemplo sintético de instrumento confirmado con mapeo.
- `docs/contracts/examples/instrument_reviewed_without_mapping.json`: Ejemplo sintético de instrumento revisado sin mapeo.

---

## 6. Verificación de Calidad

Ejecutado exhaustivamente desde `backend/`:
- **Pruebas Totales:** **493 pruebas aprobadas** (100 % pass rate):
  - `tests/research/test_instrument_models.py` (28 pruebas).
  - `tests/research/test_instrument_service.py` (27 pruebas, incluyendo 7 de integridad relacional SQLite y cascadas).
  - `tests/research/test_instrument_api.py` (19 pruebas de integración HTTP).
- **Ruff Linter:** `uv run ruff check .` $\to$ All checks passed!
- **Ruff Formatter:** `uv run ruff format --check .` $\to$ 154 files already formatted.
- **Contratos Canónicos:** `uv run python -m scripts.export_contracts --check` $\to$ Aprobado (0 discrepancias).
- **Compilación de Bytecode:** `uv run python -m compileall -q app scripts tests` $\to$ Aprobado (0 errores).
