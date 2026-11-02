"""SQLite development storage with serialized execution and retry deduplication."""

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException

from app.orchestration.analysis_models import AnalysisRecord


class SQLiteAnalysisRepository:
    def __init__(self, path: Path):
        self.path = path
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS research_analyses "
                "(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS research_analyses_project "
                "ON research_analyses(project_id)"
            )

    def add(self, record: AnalysisRecord) -> None:
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "INSERT INTO research_analyses VALUES (?, ?, ?)",
                (record.plan.id, str(record.project_id), record.storage_json()),
            )

    def list(self, project_id: UUID) -> list[AnalysisRecord]:
        with closing(sqlite3.connect(self.path)) as connection:
            rows = connection.execute(
                "SELECT payload FROM research_analyses WHERE project_id = ? ORDER BY rowid",
                (str(project_id),),
            ).fetchall()
        return [AnalysisRecord.model_validate_json(row[0]) for row in rows]

    @contextmanager
    def edit(self, project_id: UUID, plan_id: str):
        # Keep the lock through calculation: concurrent retries return the same result.
        # A process crash rolls back, so there is no permanent 'running' reservation.
        with closing(sqlite3.connect(self.path, timeout=5)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM research_analyses WHERE project_id = ? AND id = ?",
                (str(project_id), plan_id),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "No se encontró el plan en este proyecto.")
            record = AnalysisRecord.model_validate_json(row[0])
            yield record
            connection.execute(
                "UPDATE research_analyses SET payload = ? WHERE project_id = ? AND id = ?",
                (record.storage_json(), str(project_id), plan_id),
            )
