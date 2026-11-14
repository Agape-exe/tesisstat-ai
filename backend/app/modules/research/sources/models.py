from typing import Annotated, Literal

from pydantic import Field, StrictStr, model_validator

from app.shared.analysis_v2 import V2Model
from app.shared.data_sources_v2 import Moment

InputText = Annotated[StrictStr, Field(max_length=2000)]


class TableContextChanges(V2Model):
    name: Annotated[StrictStr, Field(max_length=200)] | None = None
    description: InputText | None = None
    purpose: InputText | None = None
    row_meaning: InputText | None = None
    measurement_moment: Moment | None = None
    population: InputText | None = None
    identifier_column_id: Annotated[StrictStr, Field(max_length=200)] | None = None
    related_tables_notes: InputText | None = None


class TableContextPatch(V2Model):
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    changes: TableContextChanges = Field(default_factory=TableContextChanges)
    confirm_fields: list[Annotated[StrictStr, Field(min_length=1, max_length=80)]] = Field(
        default_factory=list, max_length=8
    )


class SheetPatch(V2Model):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    action: Literal["exclude", "include", "extract"]
    header_row: Annotated[int, Field(strict=True, ge=1, le=50001)] | None = None
    range: Annotated[StrictStr, Field(max_length=40)] | None = None

    @model_validator(mode="after")
    def extraction_fields(self):
        if self.action == "extract":
            if self.header_row is None or self.range is None:
                raise ValueError("Indica encabezado y rango para extraer")
        elif self.header_row is not None or self.range is not None:
            raise ValueError("Encabezado/rango solo se aceptan para extracción")
        return self
