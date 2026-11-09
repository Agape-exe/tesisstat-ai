import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from app.modules.research.context.repository import ContextError
from app.shared.analysis_v2 import ProjectContextV2


class SQLiteContextRepository:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS research_context_revisions_v2 "
                "(project_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision >= 1), "
                "payload TEXT NOT NULL, PRIMARY KEY(project_id, revision))"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5)

    def _get(self, connection: sqlite3.Connection, project_id: str) -> ProjectContextV2 | None:
        row = connection.execute(
            "SELECT payload FROM research_context_revisions_v2 "
            "WHERE project_id = ? ORDER BY revision DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        return ProjectContextV2.model_validate_json(row[0]) if row else None

    def get(self, project_id: str) -> ProjectContextV2 | None:
        with closing(self._connect()) as connection:
            return self._get(connection, project_id)

    def revisions(self, project_id: str) -> list[ProjectContextV2]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT payload FROM research_context_revisions_v2 "
                "WHERE project_id = ? ORDER BY revision DESC",
                (project_id,),
            ).fetchall()
        return [ProjectContextV2.model_validate_json(row[0]) for row in rows]

    def append(
        self,
        project_id: str,
        expected_revision: int,
        build: Callable[[ProjectContextV2], ProjectContextV2],
    ) -> ProjectContextV2:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._get(connection, project_id) or ProjectContextV2(project_id=project_id)
            if current.revision != expected_revision:
                raise ContextError(
                    "revision_conflict",
                    "Otra edición guardó una revisión más reciente.",
                    409,
                    current_revision=current.revision,
                )
            updated = build(current)
            connection.execute(
                "INSERT INTO research_context_revisions_v2(project_id, revision, payload) "
                "VALUES (?, ?, ?)",
                (project_id, updated.revision, updated.model_dump_json()),
            )
            return updated
