"""SQLite implementation of the research instrument repository with version history."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID

from app.modules.research.instrument.contracts import InstrumentContext
from app.modules.research.instrument.repository import (
    InstrumentConflict,
    InstrumentNotFound,
    InstrumentValidationError,
)


class SQLiteInstrumentRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS research_projects (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            # Verificar si la tabla existe y si tiene foreign key declarada
            fks = connection.execute("PRAGMA foreign_key_list(research_instruments)").fetchall()
            table_info = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='research_instruments'"
            ).fetchone()
            if table_info and not fks:
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute(
                    """
                    CREATE TABLE research_instruments_fk (
                        id TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        is_current INTEGER NOT NULL DEFAULT 1,
                        payload TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (id, version),
                        FOREIGN KEY (project_id) REFERENCES research_projects(id) ON DELETE CASCADE
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO research_instruments_fk
                    SELECT id, project_id, version, status, is_current, payload,
                           created_at, updated_at
                    FROM research_instruments
                    """
                )
                connection.execute("DROP TABLE research_instruments")
                connection.execute(
                    "ALTER TABLE research_instruments_fk RENAME TO research_instruments"
                )
                connection.execute("PRAGMA foreign_keys = ON")
            else:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS research_instruments (
                        id TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        is_current INTEGER NOT NULL DEFAULT 1,
                        payload TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (id, version),
                        FOREIGN KEY (project_id) REFERENCES research_projects(id) ON DELETE CASCADE
                    )
                    """
                )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_research_instruments_project
                ON research_instruments (project_id)
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_research_instruments_current
                ON research_instruments (project_id, id) WHERE is_current = 1
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS research_instruments_cleanup
                AFTER DELETE ON research_projects
                BEGIN
                    DELETE FROM research_instruments WHERE project_id = OLD.id;
                END
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=15)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def create(self, instrument: InstrumentContext) -> InstrumentContext:
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT 1 FROM research_instruments
                    WHERE project_id = ? AND id = ? AND is_current = 1
                    """,
                    (str(instrument.project_id), str(instrument.instrument_id)),
                ).fetchone()
                if existing:
                    raise InstrumentConflict(
                        f"El instrumento '{instrument.instrument_id}' ya existe en el proyecto."
                    )

                connection.execute(
                    """
                    INSERT INTO research_instruments (
                        id, project_id, version, status, is_current, payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        str(instrument.instrument_id),
                        str(instrument.project_id),
                        instrument.version,
                        instrument.status,
                        instrument.model_dump_json(),
                        instrument.created_at.isoformat(),
                        instrument.updated_at.isoformat(),
                    ),
                )
                return instrument
        except sqlite3.IntegrityError as exc:
            if "FOREIGN KEY" in str(exc).upper():
                raise InstrumentValidationError(
                    f"El proyecto '{instrument.project_id}' no existe en la base de datos."
                ) from exc
            raise

    def get(
        self,
        project_id: UUID,
        instrument_id: UUID,
        version: int | None = None,
    ) -> InstrumentContext | None:
        with closing(self._connect()) as connection:
            if version is None:
                row = connection.execute(
                    """
                    SELECT payload FROM research_instruments
                    WHERE project_id = ? AND id = ? AND is_current = 1
                    """,
                    (str(project_id), str(instrument_id)),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT payload FROM research_instruments
                    WHERE project_id = ? AND id = ? AND version = ?
                    """,
                    (str(project_id), str(instrument_id), version),
                ).fetchone()
            return InstrumentContext.model_validate_json(row[0]) if row else None

    def list(self, project_id: UUID) -> list[InstrumentContext]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT payload FROM research_instruments
                WHERE project_id = ? AND is_current = 1
                ORDER BY updated_at DESC
                """,
                (str(project_id),),
            ).fetchall()
            return [InstrumentContext.model_validate_json(row[0]) for row in rows]

    def get_history(
        self,
        project_id: UUID,
        instrument_id: UUID,
    ) -> list[InstrumentContext]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT payload FROM research_instruments
                WHERE project_id = ? AND id = ?
                ORDER BY version ASC
                """,
                (str(project_id), str(instrument_id)),
            ).fetchall()
            return [InstrumentContext.model_validate_json(row[0]) for row in rows]

    def update(
        self,
        instrument: InstrumentContext,
        expected_version: int,
    ) -> InstrumentContext:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            current_row = connection.execute(
                """
                SELECT version, payload, status FROM research_instruments
                WHERE project_id = ? AND id = ? AND is_current = 1
                """,
                (str(instrument.project_id), str(instrument.instrument_id)),
            ).fetchone()

            if not current_row:
                raise InstrumentNotFound(
                    f"El instrumento '{instrument.instrument_id}' no existe en este proyecto."
                )

            current_ver, current_payload, current_status = current_row

            # Idempotencia: si ya está en status reviewed con misma versión y datos
            if (
                current_ver == expected_version
                and current_status == "reviewed"
                and instrument.status == "reviewed"
                and current_payload == instrument.model_dump_json()
            ):
                return instrument

            if current_ver != expected_version:
                raise InstrumentConflict(
                    f"Conflicto de concurrencia: la versión esperada ({expected_version}) "
                    f"no coincide con la versión actual persistida ({current_ver})."
                )

            new_version = expected_version + 1
            if instrument.dataset_mapping is not None:
                if instrument.dataset_mapping.instrument_version != new_version:
                    raise InstrumentConflict(
                        "La versión del dataset_mapping "
                        f"({instrument.dataset_mapping.instrument_version}) "
                        f"no coincide con la nueva versión del instrumento ({new_version})."
                    )
            persisted_inst = instrument.model_copy(update={"version": new_version})

            # Archivar la versión activa anterior
            connection.execute(
                """
                UPDATE research_instruments SET is_current = 0
                WHERE project_id = ? AND id = ? AND is_current = 1
                """,
                (str(instrument.project_id), str(instrument.instrument_id)),
            )

            # Insertar la nueva revisión histórica
            connection.execute(
                """
                INSERT INTO research_instruments (
                    id, project_id, version, status, is_current, payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    str(persisted_inst.instrument_id),
                    str(persisted_inst.project_id),
                    persisted_inst.version,
                    persisted_inst.status,
                    persisted_inst.model_dump_json(),
                    persisted_inst.created_at.isoformat(),
                    persisted_inst.updated_at.isoformat(),
                ),
            )
            return persisted_inst
