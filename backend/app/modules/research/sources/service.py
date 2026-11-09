import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.modules.research.context.repository import ContextError
from app.modules.research.datasets.readers import DatasetLimits
from app.modules.research.projects.use_cases import ProjectNotFound, ProjectService
from app.modules.research.sources.models import SheetPatch, TableContextChanges, TableContextPatch
from app.modules.research.sources.readers import WorkbookLimits, detect, extract, inventory, limit
from app.modules.research.sources.repository import SourceRepository, missing
from app.shared.analysis_v2 import Confirmation, Fact, Provenance, SourceRef, canonical_hash
from app.shared.data_sources_v2 import (
    ExtractionV2,
    ImportedTableV2,
    SourceFileV2,
    SourceSheetV2,
    TableColumnV2,
    TableContextV2,
    TablePreviewV2,
)


def sheet_hash(sheet):
    sheet.hash = canonical_hash(sheet)


def file_state(source):
    source.state = (
        "needs_clarification"
        if any(s.state in {"pending", "error"} for s in source.sheets)
        else "complete"
    )


class SourceService:
    def __init__(
        self,
        projects: ProjectService,
        repository: SourceRepository,
        limits: DatasetLimits | None = None,
        workbook_limits: WorkbookLimits | None = None,
        actor_ref: str = "local",
    ):
        self.projects = projects
        self.repository = repository
        self.limits = limits or DatasetLimits()
        self.workbook_limits = workbook_limits or WorkbookLimits()
        self.actor_ref = actor_ref

    def require(self, project_id):
        try:
            return str(self.projects.get(UUID(project_id)).id)
        except (ValueError, ProjectNotFound) as exc:
            raise ContextError("resource_not_found", "No se encontró el recurso.", 404) from exc

    def _table(self, source, sheet, extracted, confirmation=None):
        extraction = ExtractionV2(
            header_row=extracted.header_row, range=extracted.range, confirmation=confirmation
        )
        table = ImportedTableV2(
            id=str(uuid4()),
            project_id=source.project_id,
            file_id=source.id,
            sheet_id=sheet.id,
            created_at=datetime.now(UTC),
            original_hash=source.hash,
            content_hash=extracted.hash,
            extraction=extraction,
            row_count=len(extracted.rows),
            column_count=len(extracted.columns),
            columns=[
                TableColumnV2(id=str(uuid4()), name=name, position=i)
                for i, name in enumerate(extracted.columns)
            ],
            warnings=extracted.warnings,
        )
        sheet.state = "ready"
        sheet.table_id = table.id
        sheet.extraction = extraction
        sheet_hash(sheet)
        return table, extracted.data

    def add(self, project_id, name, data):
        project_id = self.require(project_id)
        name = name.strip()
        if not name or len(name) > 200 or any(c in name for c in ("/", "\\", "\x00")):
            raise ContextError(
                "invalid_payload", "Usa un nombre de archivo de hasta 200 caracteres."
            )
        format = name.rsplit(".", 1)[-1].lower()
        if format not in {"csv", "xlsx"}:
            raise ContextError("unsupported_format", "Adjunta CSV UTF-8 o XLSX sin macros.", 415)
        raw_sheets = inventory(data, format, self.limits, self.workbook_limits)
        now = datetime.now(UTC)
        source = SourceFileV2(
            id=str(uuid4()),
            project_id=project_id,
            name=name,
            format=format,
            size=len(data),
            hash=hashlib.sha256(data).hexdigest(),
            created_at=now,
            updated_at=now,
            state="needs_clarification",
            sheets=[],
        )
        tables = []
        for index, raw in enumerate(raw_sheets):
            table, explanation = detect(raw, self.limits)
            sheet = SourceSheetV2(
                id=str(uuid4()),
                project_id=project_id,
                file_id=source.id,
                index=index,
                name=raw.name,
                visibility=raw.visibility,
                row_count=len(raw.rows),
                column_count=raw.width,
                state="pending",
                explanation=explanation,
                hash="0" * 64,
            )
            if table:
                tables.append(self._table(source, sheet, table))
            sheet_hash(sheet)
            source.sheets.append(sheet)
        if sum(len(data) for _, data in tables) > self.workbook_limits.max_materialized_bytes:
            limit("Las tablas extraídas superan el límite global de 30 MiB.")
        file_state(source)
        try:
            self.repository.add(source, data, tables)
        except (OSError, sqlite3.Error) as exc:
            raise ContextError(
                "storage_unavailable", "No se publicó la importación. Reintenta la carga.", 503
            ) from exc
        return source

    def files(self, project_id):
        return self.repository.files(self.require(project_id))

    def original(self, project_id, file_id):
        source = self.repository.file(self.require(project_id), file_id)
        return source, self.repository.read("original", source.id, source.hash)

    def table(self, project_id, table_id):
        return self.repository.table(self.require(project_id), table_id)

    def tables(self, project_id):
        project_id = self.require(project_id)
        included = {
            s.table_id
            for f in self.repository.files(project_id)
            for s in f.sheets
            if s.state == "ready"
        }
        return [t for t in self.repository.tables(project_id) if t.id in included]

    def read_table(self, project_id, table_id):
        """S03B/S04 local read port. Every row, from exactly the published extraction."""
        table = self.table(project_id, table_id)
        source = self.repository.file(table.project_id, table.file_id)
        sheet = next(s for s in source.sheets if s.id == table.sheet_id)
        if sheet.state != "ready":
            raise ContextError("source_stale", "La tabla pertenece a una hoja excluida.", 409)
        content = json.loads(self.repository.read("table", table.id, table.content_hash))
        if (
            content["columns"] != [c.name for c in table.columns]
            or len(content["rows"]) != table.row_count
        ):
            raise ContextError(
                "storage_unavailable", "La extracción guardada es inconsistente.", 503
            )
        return table, content["rows"]

    def source_refs(self, project_id, table_id):
        """Resolve references on the server; no client hashes/paths are trusted."""
        table, _ = self.read_table(project_id, table_id)
        source = self.repository.file(table.project_id, table.file_id)
        sheet = next(s for s in source.sheets if s.id == table.sheet_id)
        context = self.context(project_id, table_id)
        self.repository.read("original", source.id, source.hash)
        refs = [
            SourceRef(kind="source_file", id=source.id, revision=source.revision, hash=source.hash),
            SourceRef(kind="source_sheet", id=sheet.id, revision=sheet.revision, hash=sheet.hash),
            SourceRef(kind="table", id=table.id, revision=table.revision, hash=table.content_hash),
        ]
        if context.revision:
            refs.append(
                SourceRef(
                    kind="table_context", id=table.id, revision=context.revision, hash=context.hash
                )
            )
        return refs

    def preview(self, project_id, table_id):
        table, rows = self.read_table(project_id, table_id)
        return TablePreviewV2(table=table, rows=rows[: self.limits.preview_rows])

    def change_sheet(self, project_id, file_id, sheet_id, patch: SheetPatch):
        project_id = self.require(project_id)

        def build(source, sheet):
            tables = []
            sheet.revision += 1
            source.revision += 1
            source.updated_at = datetime.now(UTC)
            if patch.action == "exclude":
                sheet.state = "excluded"
                sheet.explanation = (
                    "Excluida por ti. Se conservan el original y la extracción previa."
                )
            elif patch.action == "include":
                sheet.state = "ready" if sheet.table_id else "pending"
                sheet.explanation = (
                    "Tabla reincorporada."
                    if sheet.table_id
                    else "Confirma un encabezado y rango, o excluye esta hoja."
                )
            else:
                if sheet.table_id:
                    raise ContextError(
                        "invalid_payload",
                        "La extracción publicada es inmutable. Puedes excluirla y reincorporarla.",
                    )
                data = self.repository.read("original", source.id, source.hash)
                raw_sheets = inventory(data, source.format, self.limits, self.workbook_limits)
                if sheet.index >= len(raw_sheets) or raw_sheets[sheet.index].name != sheet.name:
                    missing()
                extracted = extract(
                    raw_sheets[sheet.index], patch.header_row, patch.range, self.limits
                )
                existing_size = sum(
                    self.repository.path("table", t.id).stat().st_size
                    for t in self.repository.tables(project_id)
                    if t.file_id == file_id
                )
                if (
                    existing_size + len(extracted.data)
                    > self.workbook_limits.max_materialized_bytes
                ):
                    limit("Las tablas extraídas superan el límite global de 30 MiB.")
                confirmation = Confirmation(
                    actor_ref=self.actor_ref,
                    confirmed_at=source.updated_at,
                    revision=sheet.revision,
                )
                tables.append(self._table(source, sheet, extracted, confirmation))
                sheet.explanation = "Encabezado y rango confirmados por ti."
            sheet_hash(sheet)
            file_state(source)
            return tables

        try:
            return self.repository.change_sheet(
                project_id, file_id, sheet_id, patch.expected_revision, build
            )
        except (OSError, sqlite3.Error) as exc:
            raise ContextError(
                "storage_unavailable", "No se guardó la selección. Reintenta.", 503
            ) from exc

    def virtual_context(self, project_id, table_id):
        context = TableContextV2(project_id=project_id, table_id=table_id, hash="0" * 64)
        context.hash = canonical_hash(context)
        return context

    def context(self, project_id, table_id):
        table = self.table(project_id, table_id)
        return self.repository.context(table.project_id, table_id) or self.virtual_context(
            table.project_id, table_id
        )

    def context_revisions(self, project_id, table_id):
        return self.repository.context_revisions(self.require(project_id), table_id)

    def contexts(self, project_id):
        return [
            self.context(project_id, t.id) for t in self.repository.tables(self.require(project_id))
        ]

    def patch_context(self, project_id, table_id, patch: TableContextPatch):
        table = self.table(project_id, table_id)
        if not patch.changes.model_fields_set and not patch.confirm_fields:
            raise ContextError("invalid_payload", "Indica cambios o campos para confirmar.")

        def build(previous):
            previous = previous or self.virtual_context(table.project_id, table_id)
            current = previous.model_copy(deep=True)
            current.revision += 1
            current.updated_at = datetime.now(UTC)
            for name in patch.changes.model_fields_set:
                value = getattr(patch.changes, name)
                value = value.strip() or None if isinstance(value, str) else value
                if name == "identifier_column_id" and value is not None:
                    if value not in {column.id for column in table.columns}:
                        raise ContextError(
                            "invalid_payload",
                            "El identificador debe ser una columna de esta tabla.",
                        )
                if value != getattr(previous, name).value:
                    setattr(current, name, Fact(value=value, provenance=Provenance(kind="manual")))
            for path in patch.confirm_fields:
                name = path.removeprefix("/")
                if path != f"/{name}" or name not in TableContextChanges.model_fields:
                    raise ContextError("invalid_payload", "Campo de confirmación desconocido.")
                fact = getattr(current, name)
                if fact.value in (None, "", "unknown"):
                    raise ContextError("invalid_payload", "Los datos desconocidos no se confirman.")
                fact.confirmation = Confirmation(
                    actor_ref=self.actor_ref,
                    confirmed_at=current.updated_at,
                    revision=current.revision,
                )
            current.hash = canonical_hash(current)
            return TableContextV2.model_validate(current.model_dump())

        return self.repository.append_context(
            table.project_id, table_id, patch.expected_revision, build
        )
