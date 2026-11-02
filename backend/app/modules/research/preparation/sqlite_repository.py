import sqlite3
from contextlib import closing
from datetime import UTC, datetime

from app.modules.research.datasets.models import Dataset, DatasetPreview
from app.modules.research.datasets.sqlite_repository import (
    DatasetStorageError,
    SQLiteDatasetRepository,
)
from app.modules.research.preparation.models import PreparationRecord


class SQLitePreparationRepository:
    def __init__(self, datasets: SQLiteDatasetRepository) -> None:
        self.datasets = datasets
        with closing(datasets._connect()) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS research_preparation_previews "
                "(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, source_id TEXT NOT NULL, "
                "plan_hash TEXT NOT NULL, source_sha256 TEXT NOT NULL, expires_at TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS research_preparations "
                "(preview_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, source_id TEXT NOT NULL, "
                "result_id TEXT NOT NULL UNIQUE, payload TEXT NOT NULL)"
            )

    def save_preview(self, preview_id, project_id, source_id, plan_hash, source_sha256, expires_at):
        with closing(self.datasets._connect()) as connection, connection:
            connection.execute(
                "DELETE FROM research_preparation_previews WHERE expires_at < ? "
                "AND id NOT IN (SELECT preview_id FROM research_preparations)",
                (datetime.now(UTC).isoformat(),),
            )
            connection.execute(
                "INSERT INTO research_preparation_previews VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(preview_id),
                    str(project_id),
                    str(source_id),
                    plan_hash,
                    source_sha256,
                    expires_at,
                ),
            )

    def get_preview(self, preview_id):
        with closing(self.datasets._connect()) as connection:
            return connection.execute(
                "SELECT project_id, source_id, plan_hash, source_sha256, expires_at "
                "FROM research_preparation_previews WHERE id = ?",
                (str(preview_id),),
            ).fetchone()

    def get_result(self, preview_id):
        with closing(self.datasets._connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM research_preparations WHERE preview_id = ?",
                (str(preview_id),),
            ).fetchone()
        return PreparationRecord.model_validate_json(row[0]) if row else None

    def apply(
        self, record: PreparationRecord, dataset: Dataset, preview: DatasetPreview, data: bytes
    ) -> PreparationRecord:
        path = self.datasets._path(dataset.id)
        try:
            with closing(self.datasets._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT payload FROM research_preparations WHERE preview_id = ?",
                    (str(record.preview_id),),
                ).fetchone()
                if row:
                    connection.rollback()
                    return PreparationRecord.model_validate_json(row[0])
                with path.open("xb") as output:
                    output.write(data)
                connection.execute(
                    "INSERT INTO research_datasets VALUES (?, ?, ?, ?, 0)",
                    (
                        str(dataset.id),
                        str(dataset.project_id),
                        dataset.model_dump_json(),
                        preview.model_dump_json(),
                    ),
                )
                connection.execute(
                    "INSERT INTO research_preparations VALUES (?, ?, ?, ?, ?)",
                    (
                        str(record.preview_id),
                        str(record.project_id),
                        str(record.source_id),
                        str(record.result_id),
                        record.model_dump_json(),
                    ),
                )
                connection.commit()
            return record
        except (OSError, sqlite3.Error) as exc:
            path.unlink(missing_ok=True)
            raise DatasetStorageError from exc

    def list(self, project_id, source_id):
        with closing(self.datasets._connect()) as connection:
            rows = connection.execute(
                "SELECT payload FROM research_preparations WHERE project_id = ? AND source_id = ? "
                "ORDER BY rowid DESC",
                (str(project_id), str(source_id)),
            ).fetchall()
        return [PreparationRecord.model_validate_json(row[0]) for row in rows]
