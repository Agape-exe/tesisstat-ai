"""Local document bytes and SQLite metadata. File names are server generated UUIDs."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID, uuid4

from app.modules.research.documents.models import Document


class DocumentStorageError(Exception):
    pass


class SQLiteDocumentRepository:
    def __init__(self, db_path: Path, storage_path: Path) -> None:
        self.db_path = db_path
        self.storage_path = storage_path.resolve()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS research_documents "
                "(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS research_documents_project "
                "ON research_documents (project_id)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=5)

    def _path(self, document_id: UUID) -> Path:
        return self.storage_path / document_id.hex

    def add(self, document: Document, data: bytes) -> None:
        path = self._path(document.id)
        try:
            with path.open("xb") as output:
                output.write(data)
            with closing(self._connect()) as connection, connection:
                connection.execute(
                    "INSERT INTO research_documents VALUES (?, ?, ?)",
                    (str(document.id), str(document.project_id), document.model_dump_json()),
                )
        except (OSError, sqlite3.Error) as exc:
            path.unlink(missing_ok=True)
            raise DocumentStorageError from exc

    def list(self, project_id: UUID) -> list[Document]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT payload FROM research_documents WHERE project_id = ? ORDER BY id",
                (str(project_id),),
            ).fetchall()
        return sorted(
            (Document.model_validate_json(row[0]) for row in rows),
            key=lambda item: item.uploaded_at,
            reverse=True,
        )

    def delete(self, project_id: UUID, document_id: UUID) -> bool:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT id FROM research_documents WHERE id = ? AND project_id = ?",
                (str(document_id), str(project_id)),
            ).fetchone()
        if row is None:
            return False
        path = self._path(document_id)
        staged = self.storage_path / f"{uuid4().hex}.deleting"
        try:
            os.replace(path, staged)
            with closing(self._connect()) as connection, connection:
                connection.execute(
                    "DELETE FROM research_documents WHERE id = ? AND project_id = ?",
                    (str(document_id), str(project_id)),
                )
            staged.unlink()
        except (OSError, sqlite3.Error) as exc:
            if staged.exists():
                os.replace(staged, path)
            raise DocumentStorageError from exc
        return True
