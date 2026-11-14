"""Local append-only C4 store. Shares the project DB lock with C2/C3 writers."""

import json
import sqlite3
from contextlib import closing, contextmanager
from typing import Protocol

from app.modules.research.sources.repository import conflict


class EvidenceStore(Protocol):
    def transaction(self): ...
    def get(self, project_id, kind, resource_id, db=None): ...
    def all(self, project_id, kind): ...
    def revisions(self, project_id, kind, resource_id): ...
    def put(self, db, project_id, kind, resource_id, payload, expected_revision): ...


class SQLiteEvidenceStore:
    def __init__(self, db_path):
        self.db_path = db_path
        with closing(self.connect()) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS analysis_evidence_v2 "
                "(project_id TEXT NOT NULL, kind TEXT NOT NULL, resource_id TEXT NOT NULL, "
                "revision INTEGER NOT NULL, payload TEXT NOT NULL, "
                "PRIMARY KEY(project_id,kind,resource_id,revision))"
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
            "SELECT payload FROM analysis_evidence_v2 WHERE project_id=? AND kind=? "
            "AND resource_id=? ORDER BY revision DESC LIMIT 1",
            (project_id, kind, resource_id),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def revisions(self, project_id, kind, resource_id):
        with closing(self.connect()) as db:
            return [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT payload FROM analysis_evidence_v2 WHERE project_id=? AND kind=? "
                    "AND resource_id=? ORDER BY revision",
                    (project_id, kind, resource_id),
                )
            ]

    def all(self, project_id, kind):
        with closing(self.connect()) as db:
            ids = db.execute(
                "SELECT DISTINCT resource_id FROM analysis_evidence_v2 "
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
            "INSERT INTO analysis_evidence_v2 VALUES (?,?,?,?,?)",
            (
                project_id,
                kind,
                resource_id,
                revision + 1,
                json.dumps(payload, ensure_ascii=False, allow_nan=False),
            ),
        )
