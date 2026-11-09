import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from app.modules.research.context.import_models import ContextSuggestion
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
            connection.execute(
                "CREATE TABLE IF NOT EXISTS context_suggestions_v2 "
                "(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, payload TEXT NOT NULL)"
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

    def create_suggestion(self, suggestion: ContextSuggestion) -> ContextSuggestion:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._get(connection, suggestion.project_id)
            revision = current.revision if current else 0
            if revision != suggestion.base_revision:
                raise ContextError(
                    "revision_conflict",
                    "El contexto cambió. Consulta la versión "
                    "actual y vuelve a revisar la respuesta.",
                    409,
                    current_revision=revision,
                )
            connection.execute(
                "INSERT INTO context_suggestions_v2 VALUES (?, ?, ?)",
                (suggestion.id, suggestion.project_id, suggestion.model_dump_json()),
            )
        return suggestion

    def list_suggestions(self, project_id: str) -> list[ContextSuggestion]:
        with closing(self._connect()) as connection:
            ids = connection.execute(
                "SELECT id FROM context_suggestions_v2 WHERE project_id = ? ORDER BY rowid DESC",
                (project_id,),
            ).fetchall()
        return [self.suggestion_operation(project_id, row[0], "read") for row in ids]

    def suggestion_operation(self, project_id, suggestion_id, operation, body=None, build=None):
        conflict = False
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM context_suggestions_v2 WHERE project_id = ? AND id = ?",
                (project_id, suggestion_id),
            ).fetchone()
            if not row:
                raise ContextError("resource_not_found", "No se encontró el recurso.", 404)
            suggestion = ContextSuggestion.model_validate_json(row[0])
            current = self._get(connection, project_id) or ProjectContextV2(project_id=project_id)
            if suggestion.state == "pending" and suggestion.base_revision != current.revision:
                suggestion.state = "stale"
            if operation == "reject" and suggestion.state == "pending":
                suggestion.state = "rejected"
            elif operation == "apply":
                if suggestion.state == "applied":
                    # Same resource is the idempotency key; return its immutable receipt.
                    return suggestion
                if (
                    suggestion.state != "pending"
                    or body.expected_revision != suggestion.base_revision
                ):
                    conflict = True
                else:
                    result = build(current, suggestion)
                    connection.execute(
                        "INSERT INTO research_context_revisions_v2 VALUES (?, ?, ?)",
                        (project_id, result.revision, result.model_dump_json()),
                    )
                    suggestion.state = "applied"
                    suggestion.result = result
                    suggestion.selected_fields = body.selected_fields
                    suggestion.applied_proposal = body.proposal
            connection.execute(
                "UPDATE context_suggestions_v2 SET payload = ? WHERE id = ? AND project_id = ?",
                (suggestion.model_dump_json(), suggestion_id, project_id),
            )
        if conflict:
            raise ContextError(
                "revision_conflict",
                "La sugerencia ya no es aplicable. "
                "Consulta el contexto y vuelve a revisar la respuesta.",
                409,
                current_revision=current.revision,
            )
        return suggestion
