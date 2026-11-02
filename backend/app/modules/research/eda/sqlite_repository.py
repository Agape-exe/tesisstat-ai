"""Local persisted EDA reports, keyed by project and dataset."""

import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel


class EDAStorageError(Exception):
    pass


class EDAReport(BaseModel):
    project_id: UUID
    dataset_id: UUID
    processed_at: str
    content_sha256: str
    rule_version: str
    summary: dict
    columns: list[dict]
    warnings: list[dict]


class SQLiteEDARepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS research_eda ("
                    "dataset_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, payload TEXT NOT NULL)"
                )
        except sqlite3.Error as exc:
            raise EDAStorageError from exc

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5)

    def get(self, project_id: UUID, dataset_id: UUID) -> EDAReport | None:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    "SELECT payload FROM research_eda WHERE project_id = ? AND dataset_id = ?",
                    (str(project_id), str(dataset_id)),
                ).fetchone()
            return EDAReport.model_validate_json(row[0]) if row else None
        except (sqlite3.Error, ValueError) as exc:
            raise EDAStorageError from exc

    def save(self, report: EDAReport) -> None:
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute(
                    "INSERT OR REPLACE INTO research_eda VALUES (?, ?, ?)",
                    (str(report.dataset_id), str(report.project_id), report.model_dump_json()),
                )
        except sqlite3.Error as exc:
            raise EDAStorageError from exc
