"""C3 table-native contracts. JSON tables never masquerade as CSV/XLSX files."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, ConfigDict, Field, StrictBool, StrictStr, model_validator

from app.shared.analysis_v2 import ID, Confirmation, Fact, Hash, SourceRef, Text, V2Model
from app.shared.data_sources_v2 import Count, Name, TableColumnV2

Scale = Literal["nominal", "ordinal", "interval", "ratio", "unknown"]
Storage = Literal["string", "integer", "number", "boolean", "date", "mixed", "unknown"]
MARKERS = ["", "NA", "N/A", "null", "none"]


class DatasetRefV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    revision: Literal[1] = 1
    hash: Hash
    hash_algorithm: Literal["table-json-v1"] = "table-json-v1"
    format: Literal["table_json"] = "table_json"
    kind: Literal["imported", "derived"]
    name: Name
    row_count: Count
    columns: list[TableColumnV2] = Field(min_length=1, max_length=200)
    synthetic: StrictBool | None = None
    source_refs: list[SourceRef]
    preparation_ref: SourceRef | None = None

    @model_validator(mode="after")
    def columns_valid(self):
        if len({c.id for c in self.columns}) != len(self.columns):
            raise ValueError("Duplicate column IDs")
        if len({c.name for c in self.columns}) != len(self.columns):
            raise ValueError("Duplicate column names")
        if [c.position for c in self.columns] != list(range(len(self.columns))):
            raise ValueError("Invalid positions")
        return self


class VariableV2(V2Model):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    id: ID
    name: Fact[Name]
    description: Fact[Text] = Field(default_factory=Fact[Text])
    measurement_scale: Fact[Scale] = Field(default_factory=lambda: Fact(value="unknown"))
    column_ids: list[ID] = Field(default_factory=list, max_length=1)
    storage_type: Storage = "unknown"
    category_order: list[StrictStr] = Field(default_factory=list, max_length=1000)
    missing_markers: list[StrictStr] = Field(default_factory=lambda: MARKERS.copy(), max_length=100)
    possible_identifier: bool = False
    identifier_confirmed: Fact[StrictBool] = Field(default_factory=Fact[StrictBool])
    field_confirmations: dict[str, Confirmation] = Field(default_factory=dict)


class VariableDictionaryV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    revision: Count = 0
    hash: Hash
    dataset_ref: DatasetRefV2
    updated_at: AwareDatetime | None = None
    variables: list[VariableV2] = Field(default_factory=list, max_length=200)
    pending_questions: list[str] = Field(default_factory=list)


class FrequencyV2(V2Model):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    value: StrictStr
    count: Count
    percentage: float


class ColumnProfileV2(V2Model):
    column_id: ID
    name: Name
    storage_type: Storage
    measurement_scale: Scale
    present: Count
    missing: Count
    distinct: Count
    constant: bool
    possible_identifier: bool
    formula_count: Count
    frequencies: list[FrequencyV2]
    numeric_summary: dict[str, str] | None = None
    warnings: list[str]


class TableProfileV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    revision: Annotated[int, Field(strict=True, ge=1)]
    hash: Hash
    dataset_ref: DatasetRefV2
    dictionary_ref: SourceRef | None
    source_refs: list[SourceRef]
    configuration_hash: Hash
    method: Literal["complete-table-descriptive"] = "complete-table-descriptive"
    engine_version: str
    missing_policy: dict[str, list[str]]
    formula_policy: Literal["text-no-evaluation"] = "text-no-evaluation"
    created_at: AwareDatetime
    state: Literal["current", "stale"] = "current"
    rows: Count
    columns_count: Count
    missing: Count
    duplicates: Count
    constant_columns: Count
    empty_columns: Count
    columns: list[ColumnProfileV2]
    warnings: list[str]


class OutputColumnV2(V2Model):
    table_id: ID
    column_id: ID
    name: Name


class PreparationOperationV2(V2Model):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    type: Literal[
        "rename_column", "drop_columns", "drop_missing", "replace_missing", "drop_duplicates"
    ]
    column_ids: list[ID] = Field(default_factory=list, max_length=200)
    new_name: Name | None = None
    value: StrictStr | None = None


class TableRecipeV2(V2Model):
    kind: Literal["prepare", "join"]
    name: Name
    left_table_id: ID
    right_table_id: ID | None = None
    left_key: ID | None = None
    right_key: ID | None = None
    key_policy: Literal["exact-text-v1"] = "exact-text-v1"
    unmatched_policy: Literal["matches_only", "all_cases"] | None = None
    columns: list[OutputColumnV2] = Field(default_factory=list, max_length=200)
    operations: list[PreparationOperationV2] = Field(default_factory=list, max_length=20)


class PreparationPreviewV2(V2Model):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=False)
    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    recipe: TableRecipeV2
    recipe_hash: Hash
    source_refs: list[SourceRef]
    configuration_hash: Hash
    result_hash: Hash
    engine_version: str
    created_at: AwareDatetime
    expires_at: AwareDatetime
    counts: dict[str, Count]
    result_columns: list[str]
    rows: list[list[StrictStr | None]]
    unmatched_left: list[Count]
    unmatched_right: list[Count]
    unmatched_left_rows: list[list[StrictStr | None]] = Field(default_factory=list)
    unmatched_right_rows: list[list[StrictStr | None]] = Field(default_factory=list)
    warnings: list[str]
    blockers: list[str]


class ColumnLineageV2(V2Model):
    source_table_id: ID
    source_column_id: ID
    result_column_id: ID | None


class DerivedTableV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    revision: Literal[1] = 1
    hash: Hash
    dataset_ref: DatasetRefV2
    preview_id: ID
    recipe: TableRecipeV2
    source_refs: list[SourceRef]
    created_at: AwareDatetime
    confirmation: Confirmation
    engine_version: str
    counts: dict[str, Count]
    column_lineage: list[ColumnLineageV2]
    # One-based source data-row indices; null means that source has no counterpart.
    row_lineage: list[dict[str, Count | None]]
    warnings: list[str]


WORKSPACE_MODELS = (
    DatasetRefV2,
    VariableDictionaryV2,
    TableProfileV2,
    TableRecipeV2,
    PreparationPreviewV2,
    DerivedTableV2,
)
