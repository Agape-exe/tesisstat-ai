from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StrictBool, StrictStr

from app.shared.analysis_v2 import ID, Hash, Text, V2Model
from app.shared.data_sources_v2 import Count, Name
from app.shared.data_workspace_v2 import Scale


class VariableChanges(V2Model):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    name: Name | None = None
    description: Text | None = None
    measurement_scale: Scale | None = None
    column_ids: list[ID] | None = Field(default=None, max_length=1)
    category_order: list[StrictStr] | None = Field(default=None, max_length=1000)
    missing_markers: list[StrictStr] | None = Field(default=None, max_length=100)
    identifier_confirmed: StrictBool | None = None


class DictionaryPatch(V2Model):
    expected_revision: Count
    dataset_revision: Annotated[int, Field(strict=True, ge=1)]
    dataset_hash: Hash
    changes: dict[ID, VariableChanges] = Field(default_factory=dict, max_length=200)
    confirm_fields: list[ID] = Field(default_factory=list, max_length=1600)


class ProfileRequest(V2Model):
    dataset_revision: Annotated[int, Field(strict=True, ge=1)]
    dataset_hash: Hash
    confirm: Literal[True]


class ApplyRequest(V2Model):
    preview_id: ID
    recipe_hash: Hash
    confirm: Literal[True]
