import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID

from app.modules.research.packages.models import StoredPackage


class SQLitePackageRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        with closing(sqlite3.connect(db_path)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS research_packages "
                "(project_id TEXT PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL)"
            )

    def get(self, project_id: UUID) -> StoredPackage | None:
        with closing(sqlite3.connect(self.db_path)) as connection:
            row = connection.execute(
                "SELECT payload FROM research_packages WHERE project_id = ?", (str(project_id),)
            ).fetchone()
        return StoredPackage.model_validate_json(row[0]) if row else None

    def find_package(self, package_id: str) -> StoredPackage | None:
        # Current development storage has one package per project; no public raw dataset path.
        with closing(sqlite3.connect(self.db_path)) as connection:
            rows = connection.execute("SELECT payload FROM research_packages").fetchall()
        for (payload,) in rows:
            record = StoredPackage.model_validate_json(payload)
            if record.package and record.package.id == package_id:
                return record
        return None

    def save(self, record: StoredPackage, expected_version: int | None) -> bool:
        with closing(sqlite3.connect(self.db_path)) as connection, connection:
            if expected_version is None:
                result = connection.execute(
                    "INSERT OR IGNORE INTO research_packages VALUES (?, ?, ?)",
                    (
                        str(record.project_id),
                        record.configuration.version,
                        record.model_dump_json(),
                    ),
                )
            else:
                result = connection.execute(
                    "UPDATE research_packages SET version = ?, payload = ? "
                    "WHERE project_id = ? AND version = ?",
                    (
                        record.configuration.version,
                        record.model_dump_json(),
                        str(record.project_id),
                        expected_version,
                    ),
                )
            return result.rowcount == 1
