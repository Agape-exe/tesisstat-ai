"""Generate C3 examples from the real services and the existing synthetic source."""

import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from uuid import NAMESPACE_URL, UUID, uuid5

from app.modules.research.data_workspace.models import ApplyRequest, DictionaryPatch, ProfileRequest
from app.modules.research.data_workspace.repository import WorkspaceRepository
from app.modules.research.data_workspace.service import WorkspaceService, encoded_table
from app.modules.research.sources.repository import SourceRepository
from app.modules.research.sources.service import SourceService
from app.shared.data_sources_v2 import ImportedTableV2, SourceFileV2
from app.shared.data_workspace_v2 import TableRecipeV2
from scripts.export_source_examples import CSV
from scripts.export_source_examples import examples as source_examples

OUTPUT = Path(__file__).resolve().parents[2] / "contracts/v2/examples"


class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 11, 9, 15, tzinfo=UTC)


def examples():
    seed = source_examples()
    table = ImportedTableV2.model_validate(seed["ImportedTableV2"])
    source = SourceFileV2.model_validate(seed["SourceFileV2"])
    rows = seed["TablePreviewV2"]["rows"]
    serial = 0

    def new_id():
        nonlocal serial
        serial += 1
        return uuid5(NAMESPACE_URL, f"s03b-example:{serial}")

    with TemporaryDirectory() as folder:
        db = Path(folder) / "example.sqlite3"
        repository = SourceRepository(db, Path(folder) / "objects")
        repository.add(source, CSV, [(table, encoded_table([c.name for c in table.columns], rows))])
        projects = SimpleNamespace(get=lambda _: SimpleNamespace(id=UUID(table.project_id)))
        service = WorkspaceService(SourceService(projects, repository), WorkspaceRepository(db))
        with (
            patch("app.modules.research.data_workspace.service.datetime", FixedClock),
            patch("app.modules.research.data_workspace.service.uuid4", new_id),
        ):
            dataset = service.dataset(table.project_id, table.id)
            dictionary = service.dictionary(table.project_id, table.id)
            variable_id = dictionary.variables[1].id
            dictionary = service.patch_dictionary(
                table.project_id,
                table.id,
                DictionaryPatch(
                    expected_revision=0,
                    dataset_revision=1,
                    dataset_hash=dataset.hash,
                    changes={
                        variable_id: {
                            "measurement_scale": "interval",
                            "identifier_confirmed": False,
                        }
                    },
                    confirm_fields=[
                        f"/variables/{variable_id}/{field}"
                        for field in (
                            "name",
                            "column_ids",
                            "measurement_scale",
                            "identifier_confirmed",
                        )
                    ],
                ),
            )
            profile = service.compute_profile(
                table.project_id,
                table.id,
                ProfileRequest(
                    dataset_revision=1,
                    dataset_hash=dataset.hash,
                    confirm=True,
                ),
            )
            recipe = TableRecipeV2(
                kind="prepare",
                name="Notas renombradas",
                left_table_id=table.id,
                operations=[
                    {
                        "type": "rename_column",
                        "column_ids": [table.columns[1].id],
                        "new_name": "nota_antes",
                    }
                ],
            )
            preview = service.preview(table.project_id, recipe)
            derived = service.apply(
                table.project_id,
                ApplyRequest(
                    preview_id=preview.id,
                    recipe_hash=preview.recipe_hash,
                    confirm=True,
                ),
            )
            return {
                type(model).__name__: model.model_dump(mode="json")
                for model in (dataset, dictionary, profile, recipe, preview, derived)
            }


def main():
    for name, payload in examples().items():
        (OUTPUT / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )


if __name__ == "__main__":
    main()
