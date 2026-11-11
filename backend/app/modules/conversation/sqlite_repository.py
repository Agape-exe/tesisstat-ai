from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from app.modules.conversation.models import Conversation, ConversationError, Message


class SQLiteConversationRepository:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, title TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS conversation_projects
                    ON conversations(project_id, updated_at DESC);
                CREATE TABLE IF NOT EXISTS conversation_requests (
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    request_id TEXT NOT NULL, content TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending','completed','failed')),
                    created_at TEXT NOT NULL, PRIMARY KEY(conversation_id, request_id));
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    request_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                    content TEXT NOT NULL, created_at TEXT NOT NULL, sequence INTEGER NOT NULL,
                    UNIQUE(conversation_id, sequence), UNIQUE(conversation_id, request_id, role));
                CREATE TRIGGER IF NOT EXISTS delete_conversation_children
                    AFTER DELETE ON conversations BEGIN
                    DELETE FROM conversation_messages WHERE conversation_id = OLD.id;
                    DELETE FROM conversation_requests WHERE conversation_id = OLD.id; END;
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(conversation_messages)")}
            if "context" not in columns:
                db.execute("ALTER TABLE conversation_messages ADD COLUMN context TEXT")
            request_columns = {
                row[1] for row in db.execute("PRAGMA table_info(conversation_requests)")
            }
            if "fingerprint" not in request_columns:
                db.execute("ALTER TABLE conversation_requests ADD COLUMN fingerprint TEXT")
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='research_projects'").fetchone():
                db.execute(
                    "CREATE TRIGGER IF NOT EXISTS delete_project_conversations "
                    "AFTER DELETE ON research_projects BEGIN "
                    "DELETE FROM conversations WHERE project_id = OLD.id; END;"
                )

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def create(self, project_id: UUID, title: str) -> Conversation:
        now = datetime.now(UTC)
        item = Conversation(
            id=uuid4(), project_id=project_id, title=title, created_at=now, updated_at=now
        )
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO conversations VALUES (?, ?, ?, ?, ?)",
                (str(item.id), str(project_id), title, now.isoformat(), now.isoformat()),
            )
        return item

    def list(self, project_id: UUID, limit: int, offset: int) -> list[Conversation]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM conversations WHERE project_id = ? "
                "ORDER BY updated_at DESC, id LIMIT ? OFFSET ?",
                (str(project_id), limit, offset),
            ).fetchall()
        return [Conversation(**dict(row)) for row in rows]

    def get(self, project_id: UUID, conversation_id: UUID) -> Conversation:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM conversations WHERE id = ? AND project_id = ?",
                (str(conversation_id), str(project_id)),
            ).fetchone()
        if row is None:
            raise ConversationError("not_found", "No se encontró la conversación.", 404)
        return Conversation(**dict(row))

    def messages(
        self,
        conversation_id: UUID,
        limit: int,
        before: int | None = None,
        *,
        completed_only: bool = False,
    ) -> list[Message]:
        condition = "AND r.status = 'completed'" if completed_only else ""
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT m.* FROM conversation_messages m JOIN conversation_requests r "
                "ON r.conversation_id=m.conversation_id AND r.request_id=m.request_id "
                f"WHERE m.conversation_id = ? AND m.sequence < ? {condition} "
                "ORDER BY m.sequence DESC LIMIT ?",
                (str(conversation_id), before or 9223372036854775807, limit),
            ).fetchall()
        return [self._message(row) for row in reversed(rows)]

    @staticmethod
    def _message(row):
        data = {k: row[k] for k in Message.model_fields}
        data["context"] = json.loads(data["context"]) if data["context"] else None
        return Message(**data)

    def _pair(self, db, cid, rid):
        return [
            self._message(row)
            for row in db.execute(
                "SELECT * FROM conversation_messages WHERE conversation_id=? AND request_id=? "
                "ORDER BY sequence",
                (cid, rid),
            ).fetchall()
        ]

    def claim(
        self,
        conversation_id: UUID,
        request_id: UUID,
        content: str,
        timeout: float,
        *,
        fingerprint: str | None = None,
        context: dict | None = None,
    ) -> list[Message] | None:
        cid, rid = str(conversation_id), str(request_id)
        now = datetime.now(UTC)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM conversation_requests WHERE conversation_id=? AND request_id=?",
                (cid, rid),
            ).fetchone()
            if row:
                if row["content"] != content or row["fingerprint"] != fingerprint:
                    raise ConversationError(
                        "idempotency_conflict", "La solicitud ya contiene otro mensaje."
                    )
                if row["status"] == "completed":
                    return self._pair(db, cid, rid)
                raise ConversationError(
                    "request_used",
                    "Solicitud en curso o fallida. Consulta el historial antes de otro envío.",
                )
            # A crashed process must not cause an automatic provider retry.
            db.execute(
                "UPDATE conversation_requests SET status='failed' WHERE conversation_id=? "
                "AND status='pending' AND created_at < ?",
                (cid, (now - timedelta(seconds=timeout + 10)).isoformat()),
            )
            if db.execute(
                "SELECT 1 FROM conversation_requests WHERE conversation_id=? AND status='pending'",
                (cid,),
            ).fetchone():
                raise ConversationError(
                    "busy", "Esta conversación ya está generando una respuesta."
                )
            db.execute(
                "INSERT INTO conversation_requests "
                "(conversation_id,request_id,content,status,created_at,fingerprint) "
                "VALUES (?, ?, ?, 'pending', ?, ?)",
                (cid, rid, content, now.isoformat(), fingerprint),
            )
            self._append(db, cid, rid, "user", content, context)
        return None

    def _append(self, db, cid, rid, role, content, context=None):
        now = datetime.now(UTC).isoformat()
        sequence = db.execute(
            "SELECT COALESCE(MAX(sequence), 0)+1 FROM conversation_messages "
            "WHERE conversation_id=?",
            (cid,),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO conversation_messages "
            "(id, conversation_id, request_id, role, content, created_at, sequence, context) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid4()),
                cid,
                rid,
                role,
                content,
                now,
                sequence,
                json.dumps(context) if context is not None else None,
            ),
        )
        db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, cid))

    def complete(
        self,
        conversation_id: UUID,
        request_id: UUID,
        content: str,
        context: dict | None = None,
        *,
        guard=None,
    ) -> list[Message]:
        cid, rid = str(conversation_id), str(request_id)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if guard:
                guard(db)
            changed = db.execute(
                "UPDATE conversation_requests SET status='completed' "
                "WHERE conversation_id=? AND request_id=? AND status='pending'",
                (cid, rid),
            ).rowcount
            if changed != 1:
                raise ConversationError(
                    "request_expired", "El envío ya no está activo. Consulta el historial."
                )
            self._append(db, cid, rid, "assistant", content, context)
            if context and context.get("consent_scope") == "tutor_context_v3":
                db.execute(
                    "UPDATE conversation_messages SET context=? "
                    "WHERE conversation_id=? AND request_id=? AND role='user'",
                    (json.dumps(context), cid, rid),
                )
            return self._pair(db, cid, rid)

    def fail(self, conversation_id: UUID, request_id: UUID, context: dict | None = None) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE conversation_requests SET status='failed' WHERE conversation_id=? "
                "AND request_id=? AND status='pending'",
                (str(conversation_id), str(request_id)),
            )
            if context is not None:
                db.execute(
                    "UPDATE conversation_messages SET context=? "
                    "WHERE conversation_id=? AND request_id=? AND role='user'",
                    (json.dumps(context), str(conversation_id), str(request_id)),
                )

    def delete(self, project_id: UUID, conversation_id: UUID) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "DELETE FROM conversations WHERE id=? AND project_id=?",
                (str(conversation_id), str(project_id)),
            )
