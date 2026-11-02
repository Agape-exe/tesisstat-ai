"""Development-only metadata and UUID-addressed file storage."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID, uuid4

from app.modules.research.datasets.models import Dataset, DatasetPreview


class DatasetStorageError(Exception):
    pass


class DatasetHasDerivatives(Exception):
    pass


class SQLiteDatasetRepository:
    def __init__(self, db_path: Path, storage_path: Path) -> None:
        self.db_path = db_path
        self.storage_path = storage_path.resolve()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS research_eda "
                "(dataset_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS research_datasets "
                "(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, payload TEXT NOT NULL, "
                "preview TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 0)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS research_datasets_project "
                "ON research_datasets(project_id)"
            )
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS research_datasets_one_active "
                "ON research_datasets(project_id) WHERE active = 1"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=5)

    def _path(self, dataset_id: UUID) -> Path:
        return self.storage_path / dataset_id.hex

    def add(self, dataset: Dataset, preview: DatasetPreview, data: bytes) -> None:
        path = self._path(dataset.id)
        try:
            with path.open("xb") as output:
                output.write(data)
            with closing(self._connect()) as connection, connection:
                connection.execute(
                    "INSERT INTO research_datasets VALUES (?, ?, ?, ?, 0)",
                    (
                        str(dataset.id),
                        str(dataset.project_id),
                        dataset.model_dump_json(),
                        preview.model_dump_json(),
                    ),
                )
        except (OSError, sqlite3.Error) as exc:
            path.unlink(missing_ok=True)
            raise DatasetStorageError from exc

    @staticmethod
    def _model(row: tuple[str, int]) -> Dataset:
        dataset = Dataset.model_validate_json(row[0])
        return dataset.model_copy(update={"active": bool(row[1])})

    def list(self, project_id: UUID) -> list[Dataset]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT payload, active FROM research_datasets "
                "WHERE project_id = ? ORDER BY rowid DESC",
                (str(project_id),),
            ).fetchall()
        return [self._model(row) for row in rows]

    def get(self, project_id: UUID, dataset_id: UUID) -> Dataset | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT payload, active FROM research_datasets WHERE project_id = ? AND id = ?",
                (str(project_id), str(dataset_id)),
            ).fetchone()
        return self._model(row) if row else None

    def preview(self, project_id: UUID, dataset_id: UUID) -> DatasetPreview | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT preview FROM research_datasets WHERE project_id = ? AND id = ?",
                (str(project_id), str(dataset_id)),
            ).fetchone()
        return DatasetPreview.model_validate_json(row[0]) if row else None

    def activate(self, project_id: UUID, dataset_id: UUID) -> bool:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE research_datasets SET active = 0 WHERE project_id = ?", (str(project_id),)
            )
            cursor = connection.execute(
                "UPDATE research_datasets SET active = 1 WHERE project_id = ? AND id = ?",
                (str(project_id), str(dataset_id)),
            )
            return cursor.rowcount == 1

    def read(self, project_id: UUID, dataset_id: UUID) -> bytes:
        if self.get(project_id, dataset_id) is None:
            raise FileNotFoundError
        try:
            return self._path(dataset_id).read_bytes()
        except OSError as exc:
            raise DatasetStorageError from exc

    def delete(self, project_id: UUID, dataset_id: UUID) -> bool:
        if self.get(project_id, dataset_id) is None:
            return False
        with closing(self._connect()) as connection:
            descendants = connection.execute(
                "SELECT payload FROM research_datasets WHERE project_id = ?",
                (str(project_id),),
            ).fetchall()
        if any(
            Dataset.model_validate_json(row[0]).source_dataset_id == dataset_id
            for row in descendants
        ):
            raise DatasetHasDerivatives
        path = self._path(dataset_id)
        staged = self.storage_path / f"{uuid4().hex}.deleting"
        try:
            os.replace(path, staged)
            with closing(self._connect()) as connection, connection:
                connection.execute(
                    "DELETE FROM research_eda WHERE project_id = ? AND dataset_id = ?",
                    (str(project_id), str(dataset_id)),
                )
                connection.execute(
                    "DELETE FROM research_datasets WHERE project_id = ? AND id = ?",
                    (str(project_id), str(dataset_id)),
                )
                if connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                    "AND name = 'research_preparations'"
                ).fetchone():
                    connection.execute(
                        "DELETE FROM research_preparations WHERE project_id = ? AND result_id = ?",
                        (str(project_id), str(dataset_id)),
                    )
                    connection.execute(
                        "DELETE FROM research_preparation_previews "
                        "WHERE project_id = ? AND source_id = ?",
                        (str(project_id), str(dataset_id)),
                    )
            staged.unlink()
        except (OSError, sqlite3.Error) as exc:
            if staged.exists():
                os.replace(staged, path)
            raise DatasetStorageError from exc
        return True
