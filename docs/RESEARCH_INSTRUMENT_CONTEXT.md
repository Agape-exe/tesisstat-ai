# InstrumentContext v1.0.0 — Especificación Técnica Definitiva (Sesión 18A-1)

## 1. Contrato Definitivo y Fuente de Verdad

El contrato canónico independiente `InstrumentContext v1.0.0` está formalmente alineado con la estructura ratificada entre el Integrante 2 (Statistics) y el Integrante 1 (Research), incorporando con absoluta precisión los cinco ajustes acordados:

1. `methodology_review_id`: Corresponde al UUID `document_id` de la revisión metodológica confirmada, validado junto con proyecto, versión y hash.
2. `dataset_version`: Se elimina formalmente de `dataset_mapping`. La vigencia utiliza `dataset_id` (UUID) y `dataset_hash` (SHA-256).
3. `reverse_rule`: Admite exclusivamente la constante `"min_plus_max_minus_value"`.
4. `InstrumentContext.status`: Admite exclusivamente `"draft"`, `"reviewed"` y `"stale"`.
5. `dataset_mapping.status`: Admite exclusivamente `"draft"`, `"confirmed"` y `"stale"`.

### Principios de Integración y Separación de Dominios
- **Propiedad Canónica:** Research es el único propietario de la persistencia y ciclo de vida de `InstrumentContext`.
- **Independencia Total de Contratos:** No se modifica `ResearchPackage v1.0.0` ni los contratos existentes de `backend/app/shared/contracts.py`.
- **Puerto de Lectura para Statistics:** Statistics accederá mediante un puerto de solo lectura desacoplado:
  ```python
  class InstrumentContextReader(Protocol):
      def get_confirmed_context(
          self,
          project_id: str,
          instrument_id: str,
      ) -> InstrumentContext: ...
  ```

---

## 2. Matriz Comparativa de Compatibilidad y Correcciones Aplicadas

| Elemento / Submodelo | Estructura Ratificada (Sesión 21B + 5 Ajustes) | Implementación Previa (18A-1 inicial) | Estado | Corrección Aplicada en Revisión Correctiva |
| :--- | :--- | :--- | :--- | :--- |
| **Confirmación Humana** | `{"state": "pending" \| "confirmed", "confirmed_at": datetime \| null, "confirmer_ref": str \| null}` | `confirmed: bool` | ❌ Incompatible | Se sustituyó `confirmed: bool` por `state: Literal["pending", "confirmed"]`. Si `state == "pending"`, las marcas temporales y de revisor son estrictamente `null`. |
| **Identificador de Ítem** | `item_id: UUID` | `id: UUID` | ❌ Incompatible | Renombrado a `item_id: UUID`. |
| **Opciones de Respuesta** | `{"code": "...", "label": "...", "numeric_value": float}` | `{"code": int, "label": str}` (sin `numeric_value`) | ❌ Incompatible | Se incorporó `numeric_value: float`. Se convirtió `code: str` para admitir códigos de texto originales ("TA", "01") sin pérdida. |
| **Reglas de Puntuación** | `{"scoring_rule_id": UUID, "scope": "dimension" \| "instrument", "dimension_id": UUID \| null, "item_ids": [UUID], "aggregation": "sum" \| "mean", "missing_policy": "all_required", "confirmed": bool}` | `{"id": UUID, "name": str, "target_type": "...", "target_id": UUID, ...}` | ❌ Incompatible | Reemplazado por la estructura acordada: `scoring_rule_id`, `scope` (`"dimension"` o `"instrument"`), `dimension_id`, `item_ids`, `aggregation`, `missing_policy="all_required"`, `confirmed`. |
| **Validación de Reglas** | Ítems de la regla deben pertenecer a la dimensión (`scope="dimension"`). | No validaba pertenencia dimensional de cada ítem de la regla. | ❌ Incompleto | Validación estricta: si `scope="dimension"`, todos los `item_ids` deben pertenecer a `dimension_id`. Si `scope="instrument"`, `dimension_id` debe ser `null`. |
| **Procedencia Documental** | `source_kind: "document" \| "manual"` con referencia a revisión metodológica obligatoria. | `source_kind: "document" \| "methodology" \| "manual"` | ❌ Incompatible | Se eliminó `"methodology"` como `source_kind`. La procedencia metodológica es obligatoria en todos los casos (`methodology_review_id`, `methodology_review_version`, `methodology_review_hash`). |
| **DatasetMapping** | `{"dataset_id": UUID, "dataset_hash": SHA256, "instrument_version": int, "item_columns": [...], "status": "draft" \| "confirmed" \| "stale", "confirmation": InstrumentConfirmation}` | Tenía `id: UUID` extra y confirmación booleana. | ❌ Incompatible | Eliminado campo `id` de mapping. Se adoptó `confirmation: InstrumentConfirmation` con `state`. Cobertura al 100 % requerida para `status="confirmed"`. |
| **Estados del Instrumento** | `status: "draft" \| "reviewed" \| "stale"`. Si `reviewed`, debe estar confirmado. | Permitía `reviewed` sin confirmación humana. | ❌ Incompleto | Se añadió regla obligatoria: si `status == "reviewed"`, `confirmation.state` debe ser obligatoriamente `"confirmed"`, y todas las reglas de puntuación deben estar confirmadas. |

---

## 3. Estructura Final de `InstrumentContext v1.0.0`

### 3.1 DTOs y Modelos Pydantic (`backend/app/modules/research/instrument/models.py`)

- **`ResponseOption`:**
  - `code: str` (1 a 100 caracteres; admite códigos originales como `"1"`, `"TA"`, `"bajo"`).
  - `label: str` (1 a 200 caracteres).
  - `numeric_value: float` (valor cuantitativo requerido por Statistics).
- **`InstrumentItem`:**
  - `item_id: UUID`
  - `variable_id: UUID`, `dimension_id: UUID`, `indicator_id: UUID`
  - `text: str` (1 a 1000 caracteres)
  - `response_type: Literal["single_choice", "numeric"]`
  - `response_options: list[ResponseOption]` ($\ge 2$ opciones con `code`, `label` y `numeric_value` únicos para `single_choice`; vacío para `numeric`)
  - `valid_min: float | None`, `valid_max: float | None` (`valid_min < valid_max`)
  - `reverse_scored: bool`
  - `reverse_rule: Literal["min_plus_max_minus_value"] | None` (obligatorio si `reverse_scored=True`; nulo si es False)
  - `source_quote: str | None`
- **`InstrumentIndicator`:** `indicator_id: UUID`, `dimension_id: UUID`, `name: str`.
- **`InstrumentDimension`:** `dimension_id: UUID`, `variable_id: UUID`, `name: str`.
- **`InstrumentVariable`:** `variable_id: UUID`, `name: str`, `scale: Literal["nominal", "ordinal", "interval", "ratio", "unknown"]`, `methodology_variable_id: UUID | None`.
- **`ScoringRule`:** `scoring_rule_id: UUID`, `scope: Literal["dimension", "instrument"]`, `dimension_id: UUID | None`, `item_ids: list[UUID]`, `aggregation: Literal["sum", "mean"]`, `missing_policy: Literal["all_required"] = "all_required"`, `confirmed: bool = False`.
- **`InstrumentProvenance`:** `source_kind: Literal["document", "manual"]`, `source_document_id: UUID | None`, `source_document_hash: Sha256Hex | None`, `methodology_review_id: UUID`, `methodology_review_version: int`, `methodology_review_hash: Sha256Hex`.
- **`InstrumentConfirmation`:** `state: Literal["pending", "confirmed"]`, `confirmed_at: datetime | None`, `confirmer_ref: str | None`.
- **`ItemColumnMapping`:** `item_id: UUID`, `column_name: str` (valida y rechaza columnas PII).
- **`DatasetMapping`:** `dataset_id: UUID`, `dataset_hash: Sha256Hex`, `instrument_version: int`, `item_columns: list[ItemColumnMapping]`, `status: Literal["draft", "confirmed", "stale"]`, `confirmation: InstrumentConfirmation`.

### 3.2 Contrato Raíz (`backend/app/modules/research/instrument/contracts.py`)

- `schema_version: Literal["1.0.0"] = "1.0.0"`
- `instrument_id: UUID`
- `project_id: UUID`
- `research_package_id: UUID | None = None`
- `version: int = 0`
- `status: Literal["draft", "reviewed", "stale"] = "draft"`
- `created_at: datetime`, `updated_at: datetime`
- `provenance: InstrumentProvenance | None = None`
- `confirmation: InstrumentConfirmation`
- `variables: list[InstrumentVariable]` ($\ge 1$)
- `dimensions: list[InstrumentDimension]` ($\ge 1$)
- `indicators: list[InstrumentIndicator]` ($\ge 1$)
- `items: list[InstrumentItem]` ($\ge 1$)
- `scoring_rules: list[ScoringRule]`
- `dataset_mapping: DatasetMapping | None = None`

---

## 4. Procedimiento para Consumo del JSON Schema por Statistics

Para que el Integrante 2 (Statistics) pueda generar o validar el esquema JSON del contrato sin depender de bases de datos internas:

```python
from app.modules.research.instrument.contracts import InstrumentContext

# Generación programática del JSON Schema estándar
schema = InstrumentContext.model_json_schema()
```

El esquema resultante:
- Declara `"additionalProperties": false` en todas las entidades (`extra="forbid"`).
- Tipifica los identificadores como cadenas UUID estándar (`format: "uuid"`).
- Restringe los enumerados (`scope`, `status`, `aggregation`, `missing_policy`, `source_kind`, `state`).
- Exporta de forma determinista las definiciones en `"$defs"`.

---

## 5. Fixtures Sintéticos Implementados

En `backend/app/modules/research/instrument/fixtures.py`:

| # | Fixture | Escenario Probado | Resultado de Validación |
|---|---|---|---|
| **1** | `make_valid_confirmed_instrument` | Instrumento confirmado con 2 ítems (uno invertido), `numeric_value`, regla dimensional, procedencia y mapeo con `state="confirmed"`. | **Válido (Pydantic OK)** |
| **2** | `make_inverted_item_without_range` | Ítem invertido (`reverse_scored=True`) con `valid_min=None`. | **Rechazado** (`ValidationError`) |
| **3** | `make_duplicate_response_options` | Alternativas de respuesta con `code="A"` repetido. | **Rechazado** (`ValidationError`) |
| **4** | `make_invalid_hierarchy_references` | Ítem con dimensión perteneciente a otra variable. | **Rechazado** (`ValidationError`) |
| **5** | `make_cross_dimensional_scoring_rule` | Regla dimensional que referencia dimensión inexistente. | **Rechazado** (`ValidationError`) |
| **6** | `make_incomplete_mapping_confirmed` | Mapeo con `status="confirmed"` que omite 1 de los 2 ítems. | **Rechazado** (`ValidationError`) |
| **7** | `make_duplicate_column_mapping` | Asignación de la misma columna de dataset a dos ítems distintos. | **Rechazado** (`ValidationError`) |
| **8** | `make_confirmed_mapping_unauthorized` | Mapeo `status="confirmed"` con `confirmation.state="pending"`. | **Rechazado** (`ValidationError`) |
| **9** | `make_incompatible_instrument_version` | Mapeo con `instrument_version` discordante con la versión del instrumento. | **Rechazado** (`ValidationError`) |
| **10** | `make_valid_reviewed_without_dataset` | Instrumento revisado confirmado (`state="confirmed"`), sin dataset asociado. | **Válido (Pydantic OK)** |

---

## 6. Pruebas Automatizadas y Calidad

- **Pruebas de Instrumento:** `uv run pytest tests/research/test_instrument_models.py tests/research/test_instrument_service.py tests/research/test_instrument_api.py` $\to$ **64 pruebas aprobadas** (100 %).
- **Pruebas Completas del Backend:** `uv run pytest` $\to$ **483 pruebas aprobadas** (100 %).
- **Verificación de Contratos Compartidos v1.0.0:** `uv run python -m scripts.export_contracts --check` $\to$ Aprobado (0 cambios a `ResearchPackage`).
- **Linters y Formato:** `uv run ruff check .` y `uv run ruff format --check .` $\to$ Aprobados con 0 errores y 153 archivos formateados.
- **Compilación de Bytecode:** `uv run python -m compileall -q app scripts tests` $\to$ Aprobado con 0 errores.

---

## 7. Persistencia SQLite y Versionado (Sesión 18A-2)

### 7.1 Esquema de Base de Datos (`research_instruments`)

La persistencia de `InstrumentContext` se implementa en SQLite mediante la tabla `research_instruments`:

```sql
CREATE TABLE IF NOT EXISTS research_instruments (
    id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (id, version),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_research_instruments_lookup
    ON research_instruments(project_id, id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_research_instruments_current
    ON research_instruments(id) WHERE is_current = 1;
```

### 7.2 Garantías de Integridad y Concurrencia Optimista
- **Clave Primaria Compuesta `(id, version)`:** Permite mantener el historial inmutable de todas las revisiones del instrumento ($v0, v1, v2, \dots$).
- **Índice Parcial Único `is_current = 1`:** Garantiza a nivel de base de datos que solo exista exactamente una versión activa para cada `instrument_id`.
- **Transacciones Atómicas (`BEGIN IMMEDIATE`):** Toda escritura serializa transacciones SQLite para evitar carreras de lectura-modificación-escritura.
- **Bloqueo Optimista (`expected_version`):** Al actualizar un borrador, vincular metodología, asociar mapeo o confirmar, se exige `expected_version`. Si la versión activa difiere, se rechaza con `InstrumentConflict`.

### 7.3 Servicios de Ciclo de Vida (`InstrumentService`)
El servicio `InstrumentService` orquesta:
1. `create_draft(project_id, variables, dimensions, indicators, items, scoring_rules)`: Genera $v0$ con estado `draft` y `confirmation.state = "pending"`.
2. `update_draft(project_id, instrument_id, expected_version, ...)`: Modifica estructura solo si `status == "draft"`, incrementando la versión y archivando la previa. Si existía un mapeo de dataset, cualquier actualización estructural invalida la confirmación previa, reseteándolo a `draft` con `pending`.
3. `link_methodology(project_id, instrument_id, expected_version, document_id, variable_links)`: Vincula a una revisión metodológica existente en estado `reviewed`, capturando su `version` y hash SHA-256. Valida la correspondencia estricta de las variables del instrumento contra las variables de la revisión metodológica (`ReviewVariable.id`).
4. `confirm_scoring_rules(project_id, instrument_id, expected_version, rule_ids)`: Confirma explícita e individualmente las reglas de puntuación sin confirmaciones automáticas implícitas.
5. `set_mapping(project_id, instrument_id, expected_version, dataset_id, item_columns)`: Valida existencia del dataset, verifica 1:1 de columnas a ítems, prohíbe columnas PII y genera mapeo en estado `draft`.
6. `confirm_mapping(project_id, instrument_id, expected_version, confirmer_ref)`: Confirma mapeo exigiendo cobertura del 100% de ítems y estado `state="confirmed"`.
7. `confirm_instrument(project_id, instrument_id, expected_version, confirmer_ref)`: Realiza confirmación humana explícita, transición a `status = "reviewed"`, exige procedencia metodológica confirmada con correspondencia estricta de variables y que TODAS las reglas de puntuación hayan sido confirmadas explícitamente de antemano.
8. `check_stale(project_id, instrument_id)`: Compara en tiempo real los hashes guardados de metodología y dataset contra los hashes vigentes.
9. `mark_stale(project_id, instrument_id, expected_version, reasons)`: Materializa de forma explícita, versionada y transaccional el estado `stale` del instrumento y su mapeo.
10. `get_history(project_id, instrument_id)`: Recupera la auditoría histórica completa ordenada cronológicamente por versión.

### 7.4 Puerto Autorizado para Statistics (`ResearchInstrumentContextReader`)
Statistics consume los instrumentos a través del protocolo desacoplado:
```python
class ResearchInstrumentContextReader:
    def __init__(self, service: InstrumentService) -> None:
        self.service = service

    def get_confirmed_context(self, project_id: str, instrument_id: str) -> InstrumentContext:
        # 1. Recupera la versión actual
        # 2. Verifica stale dinámico (rechaza si la metodología o dataset mutaron, SIN mutar base de datos en lecturas)
        # 3. Exige status == "reviewed" y confirmation.state == "confirmed"
        # 4. Si tiene dataset_mapping, exige status == "confirmed" y confirmation.state == "confirmed"
        # 5. Entrega el DTO canónico inmutable
```
Statistics nunca accede directamente a tablas o repositorios de Research. Se preserva de forma estricta la arquitectura hexagonal y la soberanía de dominios.

---

## 8. Rutas HTTP FastAPI (Sesión 18A-3 y Correcciones de Integridad)

Integradas en el entorno local de desarrollo `backend/app/modules/research/dev_app.py`:

| Método | Ruta | Código HTTP | Descripción |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/research/projects/{project_id}/instruments` | `201 Created` | Crea borrador $v0$ (`status="draft"`). Retorna header `Location`. |
| `GET` | `/api/research/projects/{project_id}/instruments` | `200 OK` | Lista todos los instrumentos activos del proyecto. |
| `GET` | `/api/research/projects/{project_id}/instruments/{instrument_id}` | `200 OK` | Obtiene el instrumento activo o histórico vía `?version=N`. |
| `PUT` | `/api/research/projects/{project_id}/instruments/{instrument_id}` | `200 OK` | Actualiza borrador exigiendo `expected_version` (concurrencia optimista e invalidación de mapeo si corresponde). |
| `POST` | `/api/research/projects/{project_id}/instruments/{instrument_id}/methodology` | `200 OK` | Vincula a una revisión metodológica confirmada validando correspondencia estricta de variables (`variable_links`). |
| `POST` | `/api/research/projects/{project_id}/instruments/{instrument_id}/rules/confirm` | `200 OK` | Confirma explícitamente reglas de puntuación específicas o todas. |
| `POST` | `/api/research/projects/{project_id}/instruments/{instrument_id}/confirm` | `200 OK` | Confirma el instrumento (`status="reviewed"`, `state="confirmed"`, exige reglas confirmadas). |
| `POST` | `/api/research/projects/{project_id}/instruments/{instrument_id}/mark-stale` | `200 OK` | Materializa explícitamente la transición transaccional a estado `stale`. |
| `POST` | `/api/research/projects/{project_id}/instruments/{instrument_id}/mapping` | `200 OK` | Establece u actualiza mapeo de dataset (`draft`, sin PII). |
| `POST` | `/api/research/projects/{project_id}/instruments/{instrument_id}/mapping/confirm` | `200 OK` | Confirma el mapeo de dataset (cobertura 100 % de ítems). |
| `GET` | `/api/research/projects/{project_id}/instruments/{instrument_id}/history` | `200 OK` | Consulta el historial completo ordenado cronológicamente por versión. |

