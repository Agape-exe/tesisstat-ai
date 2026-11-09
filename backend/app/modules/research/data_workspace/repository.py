"""SQLite adapter: complete derived JSON and metadata publish in ONE transaction.

Imported objects remain under SourceRepository's separate publication protocol.
No filesystem/SQLite atomicity is claimed for those objects.
"""

import json
import sqlite3
from contextlib import closing, contextmanager

from app.modules.research.sources.repository import conflict


class WorkspaceRepository:
    def __init__(self, db_path):
        self.db_path = db_path
        with closing(self.connect()) as db, db:
            db.executescript(
                "CREATE TABLE IF NOT EXISTS data_workspace_revisions_v2 "
                "(project_id TEXT NOT NULL, kind TEXT NOT NULL, resource_id TEXT NOT NULL, "
                "revision INTEGER NOT NULL, payload TEXT NOT NULL, "
                "PRIMARY KEY(project_id,kind,resource_id,revision));"
                "CREATE TABLE IF NOT EXISTS derived_content_v2 "
                "(project_id TEXT NOT NULL, id TEXT NOT NULL, preview_id TEXT NOT NULL, "
                "content BLOB NOT NULL, PRIMARY KEY(project_id,id), UNIQUE(project_id,preview_id));"
            )

    def connect(self):
        return sqlite3.connect(self.db_path, timeout=10)

    @contextmanager
    def transaction(self):
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            yield db

    def get(self, project_id, kind, resource_id, db=None):
        if db is None:
            with closing(self.connect()) as connection:
                return self.get(project_id, kind, resource_id, connection)
        row = db.execute(
            "SELECT payload FROM data_workspace_revisions_v2 "
            "WHERE project_id=? AND kind=? AND resource_id=? ORDER BY revision DESC LIMIT 1",
            (project_id, kind, resource_id),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def revisions(self, project_id, kind, resource_id):
        with closing(self.connect()) as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT payload FROM data_workspace_revisions_v2 "
                    "WHERE project_id=? AND kind=? AND resource_id=? ORDER BY revision",
                    (project_id, kind, resource_id),
                )
            ]

    def all(self, project_id, kind):
        with closing(self.connect()) as db:
            ids = db.execute(
                "SELECT DISTINCT resource_id FROM data_workspace_revisions_v2 "
                "WHERE project_id=? AND kind=? ORDER BY rowid",
                (project_id, kind),
            ).fetchall()
            return [self.get(project_id, kind, row[0], db) for row in ids]

    def put(self, db, project_id, kind, resource_id, payload, expected_revision):
        current = self.get(project_id, kind, resource_id, db)
        revision = current["revision"] if current else 0
        if revision != expected_revision:
            conflict(revision)
        db.execute(
            "INSERT INTO data_workspace_revisions_v2 VALUES (?,?,?,?,?)",
            (project_id, kind, resource_id, revision + 1, json.dumps(payload, ensure_ascii=False)),
        )

    def content(self, project_id, table_id):
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT content FROM derived_content_v2 WHERE project_id=? AND id=?",
                (project_id, table_id),
            ).fetchone()
        return bytes(row[0]) if row else None

    def applied(self, db, project_id, preview_id):
        row = db.execute(
            "SELECT id FROM derived_content_v2 WHERE project_id=? AND preview_id=?",
            (project_id, preview_id),
        ).fetchone()
        return self.get(project_id, "derived", row[0], db) if row else None

    def publish(self, db, record, content):
        db.execute(
            "INSERT INTO derived_content_v2 VALUES (?,?,?,?)",
            (record.project_id, record.id, record.preview_id, content),
        )
        self.put(db, record.project_id, "derived", record.id, record.model_dump(mode="json"), 0)
