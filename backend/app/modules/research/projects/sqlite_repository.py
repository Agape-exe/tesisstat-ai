"""Local development persistence only; no Supabase or shared module dependencies."""

import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID

from app.modules.research.projects.models import Project


class SQLiteProjectRepository:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS research_projects "
                "(id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL, owner_id TEXT DEFAULT 'local')"
            )
            cols = [r[1] for r in connection.execute("PRAGMA table_info(research_projects)").fetchall()]
            if "owner_id" not in cols:
                connection.execute("ALTER TABLE research_projects ADD COLUMN owner_id TEXT DEFAULT 'local'")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_research_projects_owner ON research_projects(owner_id)")

    def _connect(self) -> sqlite3.Connection:
        # One connection per operation: usable by FastAPI worker threads.
        return sqlite3.connect(self.path, timeout=5)

    def list(self, owner_id: str | None = None) -> list[Project]:
        with closing(self._connect()) as connection:
            if owner_id and owner_id != "*":
                rows = connection.execute(
                    "SELECT payload FROM research_projects WHERE owner_id = ? ORDER BY updated_at DESC, id",
                    (owner_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT payload FROM research_projects ORDER BY updated_at DESC, id"
                ).fetchall()
        return [Project.model_validate_json(row[0]) for row in rows]

    def get(self, project_id: UUID) -> Project | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM research_projects WHERE id = ?", (str(project_id),)
            ).fetchone()
        return Project.model_validate_json(row[0]) if row else None

    def get_owner(self, project_id: UUID) -> str | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT owner_id FROM research_projects WHERE id = ?", (str(project_id),)
            ).fetchone()
        return row[0] if row and row[0] else None

    def add(self, project: Project, owner_id: str = "local") -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO research_projects (id, payload, updated_at, owner_id) VALUES (?, ?, ?, ?)",
                (str(project.id), project.model_dump_json(), project.updated_at.isoformat(), owner_id),
            )

    def replace(self, project: Project) -> bool:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE research_projects SET payload = ?, updated_at = ? WHERE id = ?",
                (project.model_dump_json(), project.updated_at.isoformat(), str(project.id)),
            )
            return cursor.rowcount == 1

    def delete(self, project_id: UUID) -> bool:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "DELETE FROM research_projects WHERE id = ?", (str(project_id),)
            )
            return cursor.rowcount == 1
