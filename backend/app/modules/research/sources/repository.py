"""Local publication: immutable objects first, one SQLite transaction second.

Pending manifests survive process interruption. Recovery never guesses object keys.
"""

import hashlib
import json
import os
import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from uuid import UUID, uuid4

from app.modules.research.context.repository import ContextError
from app.shared.data_sources_v2 import ImportedTableV2, SourceFileV2, TableContextV2


def missing():
    raise ContextError("resource_not_found", "No se encontró el recurso.", 404)


def conflict(revision: int):
    raise ContextError(
        "revision_conflict",
        "Otra edición guardó una revisión más reciente. Tu borrador sigue disponible.",
        409,
        current_revision=revision,
    )


class SourceRepository:
    """SQLite adapter. Every lookup includes project scope and validates parent linkage."""

    def __init__(self, db_path: Path, storage_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.storage_path = storage_path.resolve()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.executescript(
                "CREATE TABLE IF NOT EXISTS source_files_v2 "
                "(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, payload TEXT NOT NULL);"
                "CREATE INDEX IF NOT EXISTS source_files_project_v2 "
                "ON source_files_v2(project_id);"
                "CREATE TABLE IF NOT EXISTS imported_tables_v2 "
                "(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, file_id TEXT NOT NULL, "
                "sheet_id TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, "
                "FOREIGN KEY(file_id) REFERENCES source_files_v2(id));"
                "CREATE INDEX IF NOT EXISTS imported_tables_project_v2 "
                "ON imported_tables_v2(project_id);"
                "CREATE TABLE IF NOT EXISTS table_context_revisions_v2 "
                "(table_id TEXT NOT NULL, project_id TEXT NOT NULL, revision INTEGER NOT NULL, "
                "payload TEXT NOT NULL, PRIMARY KEY(table_id,revision), "
                "FOREIGN KEY(table_id) REFERENCES imported_tables_v2(id));"
                "CREATE TABLE IF NOT EXISTS source_file_revisions_v2 "
                "(file_id TEXT NOT NULL, project_id TEXT NOT NULL, revision INTEGER NOT NULL, "
                "payload TEXT NOT NULL, PRIMARY KEY(file_id,revision));"
            )

    def connect(self):
        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def path(self, kind: str, resource_id: str):
        if kind not in {"original", "table"}:
            raise ValueError("Invalid storage kind")
        return self.storage_path / f"{UUID(resource_id).hex}.{kind}"

    def _file(self, db, project_id: str, file_id: str):
        row = db.execute(
            "SELECT payload FROM source_files_v2 WHERE project_id=? AND id=?",
            (project_id, file_id),
        ).fetchone()
        if row is None:
            missing()
        return SourceFileV2.model_validate_json(row[0])

    def file(self, project_id: str, file_id: str):
        with closing(self.connect()) as db:
            return self._file(db, project_id, file_id)

    def files(self, project_id: str):
        with closing(self.connect()) as db:
            rows = db.execute(
                "SELECT payload FROM source_files_v2 WHERE project_id=? ORDER BY rowid DESC",
                (project_id,),
            ).fetchall()
        return [SourceFileV2.model_validate_json(row[0]) for row in rows]

    def table(self, project_id: str, table_id: str):
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT t.payload FROM imported_tables_v2 t JOIN source_files_v2 f "
                "ON t.file_id=f.id AND t.project_id=f.project_id "
                "WHERE t.project_id=? AND t.id=?",
                (project_id, table_id),
            ).fetchone()
            if row is None:
                missing()
            table = ImportedTableV2.model_validate_json(row[0])
            source = self._file(db, project_id, table.file_id)
            if not any(s.id == table.sheet_id and s.table_id == table.id for s in source.sheets):
                missing()
            return table

    def tables(self, project_id: str):
        with closing(self.connect()) as db:
            rows = db.execute(
                "SELECT id FROM imported_tables_v2 WHERE project_id=? ORDER BY rowid",
                (project_id,),
            ).fetchall()
        return [self.table(project_id, row[0]) for row in rows]

    def read(self, kind: str, resource_id: str, expected_hash: str) -> bytes:
        try:
            data = self.path(kind, resource_id).read_bytes()
            if hashlib.sha256(data).hexdigest() != expected_hash:
                raise OSError("Object hash mismatch")
            return data
        except OSError as exc:
            raise ContextError(
                "storage_unavailable", "La fuente guardada no está disponible o está dañada.", 503
            ) from exc

    def _objects(self, objects: list[tuple[str, str, bytes]], publish: Callable):
        manifest = self.storage_path / f"{uuid4().hex}.pending.json"
        created: list[Path] = []
        try:
            with manifest.open("x", encoding="utf-8") as journal:
                journal.write(
                    json.dumps(
                        [
                            {"kind": kind, "id": key, "hash": hashlib.sha256(data).hexdigest()}
                            for kind, key, data in objects
                        ]
                    )
                )
                journal.flush()
                os.fsync(journal.fileno())
            for kind, key, data in objects:
                path = self.path(kind, key)
                with path.open("xb") as output:
                    created.append(path)
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                self.read(kind, key, hashlib.sha256(data).hexdigest())
            publish()
        except Exception:
            # Process death may leave a manifest; ordinary failures roll back new objects.
            for path in created:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            if all(not path.exists() for path in created):
                manifest.unlink(missing_ok=True)
            raise
        else:
            # Metadata is already committed: cleanup failure must not erase published data.
            try:
                manifest.unlink(missing_ok=True)
            except OSError:
                pass

    def _insert_tables(self, db, tables):
        for table, _ in tables:
            db.execute(
                "INSERT INTO imported_tables_v2 VALUES(?,?,?,?,?)",
                (
                    table.id,
                    table.project_id,
                    table.file_id,
                    table.sheet_id,
                    table.model_dump_json(),
                ),
            )

    def _record_file(self, db, source):
        db.execute(
            "INSERT INTO source_file_revisions_v2 VALUES(?,?,?,?)",
            (source.id, source.project_id, source.revision, source.model_dump_json()),
        )

    def add(self, source: SourceFileV2, original: bytes, tables):
        def publish():
            with closing(self.connect()) as db, db:
                db.execute(
                    "INSERT INTO source_files_v2 VALUES(?,?,?)",
                    (source.id, source.project_id, source.model_dump_json()),
                )
                self._insert_tables(db, tables)
                self._record_file(db, source)

        self._objects(
            [("original", source.id, original)] + [("table", t.id, data) for t, data in tables],
            publish,
        )

    def change_sheet(self, project_id, file_id, sheet_id, expected_revision, build):
        # Serialize CAS, extraction and publication for the same SQLite store.
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            source = self._file(db, project_id, file_id)
            sheet = next((s for s in source.sheets if s.id == sheet_id), None)
            if sheet is None:
                missing()
            if sheet.revision != expected_revision:
                conflict(sheet.revision)
            tables = build(source, sheet)

            def publish():
                db.execute(
                    "UPDATE source_files_v2 SET payload=? WHERE project_id=? AND id=?",
                    (source.model_dump_json(), project_id, file_id),
                )
                self._insert_tables(db, tables)
                self._record_file(db, source)
                db.commit()

            self._objects([("table", t.id, data) for t, data in tables], publish)
            return source

    def _context(self, db, project_id, table_id):
        row = db.execute(
            "SELECT payload FROM table_context_revisions_v2 WHERE project_id=? AND table_id=? "
            "ORDER BY revision DESC LIMIT 1",
            (project_id, table_id),
        ).fetchone()
        return TableContextV2.model_validate_json(row[0]) if row else None

    def context(self, project_id, table_id):
        self.table(project_id, table_id)
        with closing(self.connect()) as db:
            return self._context(db, project_id, table_id)

    def context_revisions(self, project_id, table_id):
        self.table(project_id, table_id)
        with closing(self.connect()) as db:
            rows = db.execute(
                "SELECT payload FROM table_context_revisions_v2 WHERE project_id=? AND table_id=? "
                "ORDER BY revision DESC",
                (project_id, table_id),
            ).fetchall()
        return [TableContextV2.model_validate_json(row[0]) for row in rows]

    def append_context(self, project_id, table_id, expected_revision, build):
        self.table(project_id, table_id)
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            previous = self._context(db, project_id, table_id)
            if (previous.revision if previous else 0) != expected_revision:
                conflict(previous.revision if previous else 0)
            context = build(previous)
            db.execute(
                "INSERT INTO table_context_revisions_v2 VALUES(?,?,?,?)",
                (table_id, project_id, context.revision, context.model_dump_json()),
            )
            return context

    def recover(self, apply=False):
        """Explicit local maintenance; retain all DB-referenced objects and verify hashes."""
        report = []
        with closing(self.connect()) as db:
            for manifest in self.storage_path.glob("*.pending.json"):
                objects = json.loads(manifest.read_text(encoding="utf-8"))
                for item in objects:
                    kind, key = item["kind"], item["id"]
                    path = self.path(kind, key)
                    table_name = "source_files_v2" if kind == "original" else "imported_tables_v2"
                    exists = db.execute(f"SELECT 1 FROM {table_name} WHERE id=?", (key,)).fetchone()
                    if exists:
                        self.read(kind, key, item["hash"])
                    elif apply:
                        path.unlink(missing_ok=True)
                    report.append({"id": key, "kind": kind, "published": bool(exists)})
                if apply:
                    manifest.unlink()
        return report
