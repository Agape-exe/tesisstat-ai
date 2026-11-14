"""C3 sources: immutable original/extraction/content, separately revisioned context."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, ConfigDict, Field, StrictStr, model_serializer, model_validator

from app.shared.analysis_v2 import ID, Confirmation, Fact, Hash, Revision, Text, V2Model

Moment = Literal["before", "after", "other", "unknown"]
Name = Annotated[str, Field(min_length=1, max_length=200)]
Count = Annotated[int, Field(strict=True, ge=0)]


class ExtractionV2(V2Model):
    header_row: Annotated[int, Field(strict=True, ge=1)]
    range: Annotated[str, Field(pattern=r"^[A-Z]+[1-9][0-9]*:[A-Z]+[1-9][0-9]*$")]
    algorithm_version: Literal["tabular-v1", "tabular-v2"] = "tabular-v1"
    confirmation: Confirmation | None = None


class TableColumnV2(V2Model):
    id: ID
    name: Name
    position: Count
    source_column: Annotated[str, Field(pattern=r"^[A-Z]+$")] | None = None
    formula_count: Count = 0
    formula_error_count: Count = 0

    @model_serializer(mode="wrap")
    def compatible_payload(self, handler):
        # Keep hashes/tokens of persisted pre-C01 dictionaries and snapshots exact.
        payload = handler(self)
        for key in ("source_column", "formula_count", "formula_error_count"):
            if payload.get(key) in (None, 0):
                payload.pop(key, None)
        return payload


class FormulaValueV2(V2Model):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    coordinate: str
    formula: str
    value: StrictStr | None
    status: Literal["calculated", "error"]
    error: str | None
    dependencies: list[str]


class FormulaAuditV2(V2Model):
    engine_version: Literal["excel-subset-1"]
    cache_policy: Literal["ignored"] = "ignored"
    formulas: list[FormulaValueV2]
    cell_types: list[
        list[Literal["blank", "text", "number", "boolean", "date", "formula", "error"]]
    ]


class ImportedTableV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    file_id: ID
    sheet_id: ID
    revision: Literal[1] = 1
    created_at: AwareDatetime
    original_hash: Hash
    content_hash: Hash
    hash_algorithm: Literal["table-json-v1"] = "table-json-v1"
    extraction: ExtractionV2
    row_count: Count
    column_count: Annotated[int, Field(strict=True, ge=1)]
    columns: list[TableColumnV2]
    warnings: list[str] = Field(default_factory=list)
    omitted_columns: list[str] = Field(default_factory=list)
    calculation_version: str | None = None

    @model_validator(mode="after")
    def columns_match(self):
        if self.column_count != len(self.columns):
            raise ValueError("Column count mismatch")
        if len({c.id for c in self.columns}) != len(self.columns):
            raise ValueError("Duplicate column IDs")
        if [c.position for c in self.columns] != list(range(len(self.columns))):
            raise ValueError("Invalid column positions")
        return self


class SourceSheetV2(V2Model):
    id: ID
    project_id: ID
    file_id: ID
    revision: Revision = 1
    index: Count
    name: Name
    visibility: Literal["visible", "hidden", "veryHidden"] = "visible"
    row_count: Count
    column_count: Count
    state: Literal["ready", "pending", "excluded", "error"]
    explanation: Text
    hash: Hash
    table_id: ID | None = None
    extraction: ExtractionV2 | None = None


class SourceFileV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    revision: Revision = 1
    name: Name
    format: Literal["csv", "xlsx"]
    size: Annotated[int, Field(strict=True, ge=1)]
    hash: Hash
    hash_algorithm: Literal["sha256-bytes"] = "sha256-bytes"
    created_at: AwareDatetime
    updated_at: AwareDatetime
    state: Literal["complete", "needs_clarification"]
    sheets: list[SourceSheetV2]
    reimported_from: ID | None = None

    @model_validator(mode="after")
    def parents(self):
        if len({s.id for s in self.sheets}) != len(self.sheets):
            raise ValueError("Duplicate sheets")
        if any(s.file_id != self.id or s.project_id != self.project_id for s in self.sheets):
            raise ValueError("Invalid sheet parent")
        return self


class TablePreviewV2(V2Model):
    # Context text is trimmed; observational cell values must remain exact.
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=False)
    table: ImportedTableV2
    rows: list[list[StrictStr | None]]
    formula_cells: list[FormulaValueV2] = Field(default_factory=list)


class TableContextV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    project_id: ID
    table_id: ID
    revision: Count = 0
    hash: Hash
    updated_at: AwareDatetime | None = None
    name: Fact[Name] = Field(default_factory=Fact[Name])
    description: Fact[Text] = Field(default_factory=Fact[Text])
    purpose: Fact[Text] = Field(default_factory=Fact[Text])
    row_meaning: Fact[Text] = Field(default_factory=Fact[Text])
    measurement_moment: Fact[Moment] = Field(default_factory=lambda: Fact(value="unknown"))
    population: Fact[Text] = Field(default_factory=Fact[Text])
    identifier_column_id: Fact[ID] = Field(default_factory=Fact[ID])
    related_tables_notes: Fact[Text] = Field(default_factory=Fact[Text])

    @model_validator(mode="after")
    def virtual_date(self):
        if (self.revision == 0) != (self.updated_at is None):
            raise ValueError("Only virtual context has no date")
        return self


DATA_SOURCE_MODELS = (
    FormulaAuditV2,
    SourceFileV2,
    SourceSheetV2,
    ImportedTableV2,
    TableContextV2,
    TablePreviewV2,
)
