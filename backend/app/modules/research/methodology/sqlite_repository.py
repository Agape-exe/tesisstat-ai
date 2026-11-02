import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID

from app.modules.research.documents.use_cases import DocumentNotFound
from app.modules.research.methodology.models import MethodologyState
from app.shared.ai_errors import AIError


class SQLiteMethodologyRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS research_methodology "
                "(document_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TRIGGER IF NOT EXISTS research_methodology_cleanup "
                "AFTER DELETE ON research_documents BEGIN "
                "DELETE FROM research_methodology WHERE document_id = OLD.id; END"
            )

    def _connect(self):
        return sqlite3.connect(self.db_path, timeout=5)

    def get(self, project_id: UUID, document_id: UUID) -> MethodologyState | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM research_methodology WHERE project_id=? AND document_id=?",
                (str(project_id), str(document_id)),
            ).fetchone()
        return MethodologyState.model_validate_json(row[0]) if row else None

    @staticmethod
    def _write(connection, result):
        cursor = connection.execute(
            "INSERT INTO research_methodology (document_id, project_id, payload) "
            "SELECT ?, ?, ? WHERE EXISTS "
            "(SELECT 1 FROM research_documents WHERE id=? AND project_id=?) "
            "ON CONFLICT(document_id) DO UPDATE SET payload=excluded.payload",
            (
                str(result.document_id),
                str(result.project_id),
                result.model_dump_json(),
                str(result.document_id),
                str(result.project_id),
            ),
        )
        if not cursor.rowcount:
            raise DocumentNotFound

    def claim(self, project_id, document_id, now, lease, max_attempts):
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM research_methodology WHERE project_id=? AND document_id=?",
                (str(project_id), str(document_id)),
            ).fetchone()
            state = (
                MethodologyState.model_validate_json(row[0])
                if row
                else MethodologyState(project_id=project_id, document_id=document_id)
            )
            if (
                state.status == "completed"
                or state.attempts >= max_attempts
                or (state.retry_after and state.retry_after > now)
            ):
                return state, False
            state.status = "processing"
            state.attempts += 1
            state.retry_after = lease
            state.error_code = state.message = None
            self._write(connection, state)
            return state, True

    def save(self, result: MethodologyState) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM research_methodology WHERE project_id=? AND document_id=?",
                (str(result.project_id), str(result.document_id)),
            ).fetchone()
            if row and MethodologyState.model_validate_json(row[0]).attempts != result.attempts:
                raise AIError("busy")
            self._write(connection, result)
