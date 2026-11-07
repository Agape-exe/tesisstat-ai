"""Project-scoped Research inputs for an eventual Statistics consumer.

This is an internal orchestration service. It is designed to compose verified
Research assets (such as confirmed InstrumentContext and authorized dataset rows)
for consumption by Statistics or internal analysis pipelines.

Security & Authorization note:
- This service operates as an internal subsystem bridge.
- Validating project membership does NOT substitute for end-user authorization.
- The external caller (e.g., API router or application boundary) must perform user authentication
  and verify tenant/user permissions before invoking this composition.
- This service never accepts raw filesystem paths or arbitrary table names.
- This service never exposes raw dataset bytes over HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.research.datasets.hashing import compute_dataset_hash
from app.modules.research.datasets.readers import (
    InvalidDataset,
    iter_dataset,
    read_csv,
    read_xlsx,
)
from app.modules.research.datasets.sqlite_repository import DatasetStorageError
from app.modules.research.datasets.use_cases import DatasetNotFound, DatasetService
from app.modules.research.instrument.reader import ResearchInstrumentContextReader
from app.modules.research.instrument.repository import (
    InstrumentNotConfirmedError,
    InstrumentNotFound,
    InstrumentStaleError,
)
from app.modules.research.packages.reader import PackageReaderAdapter
from app.modules.research.packages.use_cases import PackageService
from app.modules.research.projects.use_cases import ProjectNotFound, ProjectService
from app.shared.contracts import DatasetReference, ResearchPackage

if TYPE_CHECKING:
    from app.modules.research.instrument.service import InstrumentService
    from app.shared.instrument_contracts import InstrumentContext
    from app.shared.ports import InstrumentContextReader

__all__ = [
    "AuthorizedInstrumentData",
    "InstrumentStatisticsBridge",
    "ResearchInputError",
    "ResearchStatisticsBridge",
]


class ResearchInputError(Exception):
    """A safe, typed failure at the Research/Statistics boundary."""

    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(detail)


@dataclass(frozen=True)
class AuthorizedInstrumentData:
    """Authorized composition of confirmed InstrumentContext and verified dataset rows.

    Contains the canonical InstrumentContext DTO, row mappings restricted strictly
    to authorized mapped columns, and the list of included column names.
    Exposes no filesystem paths, internal storage keys, or raw file bytes.
    """

    context: InstrumentContext
    rows: tuple[dict[str, object], ...]
    column_names: tuple[str, ...]

    def __iter__(self):
        """Allow unpacking as (context, rows)."""
        return iter((self.context, self.rows))


class InstrumentStatisticsBridge:
    """Internal orchestration service delivering authorized InstrumentContext and dataset rows."""

    def __init__(
        self,
        projects: ProjectService,
        datasets: DatasetService,
        instruments: InstrumentService,
        instrument_reader: InstrumentContextReader | None = None,
    ) -> None:
        self.projects = projects
        self.datasets = datasets
        self.instruments = instruments
        self.reader = instrument_reader or ResearchInstrumentContextReader(instruments)

    def get_authorized_instrument_data(
        self,
        project_id: UUID | str,
        instrument_id: UUID | str,
        scoring_rule_id: UUID | str | None = None,
    ) -> AuthorizedInstrumentData:
        """Compose a confirmed InstrumentContext and verified dataset rows for Statistics.

        Performs strict verification across:
        1. Project and instrument identity and ownership.
        2. Reviewed status and human confirmation of instrument and dataset mapping.
        3. Freshness / staleness pre- and post-read.
        4. Matching instrument version with mapping version.
        5. Complete coverage of all instrument items in mapping.
        6. Optional filtering to columns needed by a specific confirmed scoring rule.
        7. Dataset project ownership, identity, size, and SHA-256 metadata+bytes hash match.
        8. File structure validation via iter_dataset, detecting uncalculated formulas.
        9. Delivery of rows restricted strictly to authorized mapped columns (no extraneous data).
        10. Detection of concurrent modifications before handing rows to callers.
        """
        # 1. Validar identificadores
        try:
            proj_uuid = UUID(str(project_id))
            inst_uuid = UUID(str(instrument_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ResearchInputError(
                "invalid_reference",
                "Los identificadores de proyecto e instrumento deben ser UUID válidos.",
            ) from exc

        # 2. Validar existencia del proyecto
        try:
            self.projects.get(proj_uuid)
        except ProjectNotFound as exc:
            raise ResearchInputError("project_missing", "No se encontró el proyecto.") from exc

        # 3. Validar existencia del instrumento y pertenencia al proyecto
        try:
            instrument = self.instruments.get(proj_uuid, inst_uuid)
        except InstrumentNotFound as exc:
            raise ResearchInputError(
                "instrument_missing",
                "El instrumento no existe o no pertenece al proyecto.",
            ) from exc
        except (ValidationError, ValueError) as exc:
            msg = str(exc)
            if "dataset_mapping" in msg and ("versión" in msg or "version" in msg):
                code = "mapping_version_mismatch"
            elif "sin mapear" in msg or "cubrir todos los ítems" in msg:
                code = "mapping_incomplete"
            else:
                code = "instrument_invalid"
            raise ResearchInputError(
                code, "El instrumento persistido no es válido según su contrato."
            ) from exc

        if instrument.project_id != proj_uuid:
            raise ResearchInputError(
                "instrument_missing",
                "El instrumento no pertenece al proyecto especificado.",
            )

        # 4. Obtener contexto mediante el puerto autorizado real
        try:
            context = self.reader.get_confirmed_context(str(proj_uuid), str(inst_uuid))
        except InstrumentNotFound as exc:
            raise ResearchInputError("instrument_missing", str(exc)) from exc
        except InstrumentNotConfirmedError as exc:
            code = (
                "mapping_not_confirmed"
                if "mapeo" in str(exc).lower()
                else "instrument_not_confirmed"
            )
            raise ResearchInputError(code, str(exc)) from exc
        except InstrumentStaleError as exc:
            raise ResearchInputError("instrument_stale", str(exc)) from exc
        except (ValidationError, ValueError) as exc:
            msg = str(exc)
            if "dataset_mapping" in msg and ("versión" in msg or "version" in msg):
                code = "mapping_version_mismatch"
            elif "sin mapear" in msg or "cubrir todos los ítems" in msg:
                code = "mapping_incomplete"
            else:
                code = "instrument_invalid"
            raise ResearchInputError(
                code, "El instrumento persistido no es válido según su contrato."
            ) from exc
        except Exception as exc:
            raise ResearchInputError(
                "instrument_error", "Error al recuperar el instrumento."
            ) from exc

        # 5. Validar requisitos del mapeo de datos
        if context.dataset_mapping is None:
            raise ResearchInputError(
                "mapping_missing",
                "El instrumento no tiene un mapeo de dataset configurado.",
            )

        mapping = context.dataset_mapping
        if mapping.status != "confirmed":
            raise ResearchInputError(
                "mapping_not_confirmed",
                "El mapeo de dataset no está confirmado.",
            )

        if mapping.confirmation.state != "confirmed":
            raise ResearchInputError(
                "mapping_not_confirmed",
                "La confirmación humana del mapeo de dataset está pendiente.",
            )

        if mapping.instrument_version != context.version:
            raise ResearchInputError(
                "mapping_version_mismatch",
                "El mapeo no corresponde a la versión actual del instrumento.",
            )

        # Cobertura íntegra de ítems según contrato público
        inst_item_ids = {it.item_id for it in context.items}
        mapped_item_ids = {m.item_id for m in mapping.item_columns}
        if inst_item_ids != mapped_item_ids:
            raise ResearchInputError(
                "mapping_incomplete",
                "El mapeo de dataset debe cubrir el 100% de los ítems del instrumento.",
            )

        if len(mapping.item_columns) != len(mapped_item_ids):
            raise ResearchInputError(
                "mapping_corrupt",
                "Existen ítems repetidos en la asignación de columnas del mapeo.",
            )

        if any(not m.column_name or not m.column_name.strip() for m in mapping.item_columns):
            raise ResearchInputError(
                "mapping_corrupt",
                "Las columnas mapeadas no pueden estar vacías.",
            )

        # 6. Selección de columnas según scoring_rule_id opcional
        if scoring_rule_id is not None:
            rule_str = str(scoring_rule_id)
            rule = next(
                (r for r in context.scoring_rules if str(r.scoring_rule_id) == rule_str),
                None,
            )
            if rule is None:
                raise ResearchInputError(
                    "scoring_rule_missing",
                    f"La regla de puntuación '{scoring_rule_id}' no existe en el instrumento.",
                )
            if not rule.confirmed:
                raise ResearchInputError(
                    "scoring_rule_not_confirmed",
                    f"La regla de puntuación '{scoring_rule_id}' no está confirmada.",
                )
            target_item_ids = set(rule.item_ids)
            target_columns = [
                m.column_name for m in mapping.item_columns if m.item_id in target_item_ids
            ]
        else:
            target_columns = [m.column_name for m in mapping.item_columns]

        seen: set[str] = set()
        ordered_target_columns: list[str] = []
        for c in target_columns:
            if c not in seen:
                seen.add(c)
                ordered_target_columns.append(c)

        # 7. Validar existencia del dataset y pertenencia al proyecto
        dataset_id = mapping.dataset_id
        try:
            dataset = self.datasets.get(proj_uuid, dataset_id)
        except DatasetNotFound as exc:
            raise ResearchInputError(
                "dataset_inaccessible",
                "El dataset vinculado no existe en el proyecto.",
            ) from exc

        if dataset.project_id != proj_uuid:
            raise ResearchInputError(
                "dataset_inaccessible",
                "El dataset no pertenece al proyecto.",
            )

        if dataset.id != dataset_id:
            raise ResearchInputError(
                "dataset_inaccessible",
                "El dataset no coincide con el mapeo.",
            )

        if dataset.format not in ("csv", "xlsx"):
            raise ResearchInputError(
                "dataset_invalid_format",
                "El formato del dataset no es compatible.",
            )

        dataset_col_set = set(dataset.columns)
        missing_in_dataset = [c for c in ordered_target_columns if c not in dataset_col_set]
        if missing_in_dataset:
            raise ResearchInputError(
                "mapping_column_missing",
                f"Las columnas mapeadas no existen en el dataset: {', '.join(missing_in_dataset)}.",
            )

        # 8. Vigencia de las fuentes antes de leer el dataset
        is_stale, reasons = self.instruments.check_stale(proj_uuid, inst_uuid)
        if is_stale or context.status == "stale":
            raise ResearchInputError(
                "instrument_stale",
                f"El instrumento está desactualizado respecto a sus fuentes: {', '.join(reasons)}",
            )

        # 9. Lectura de bytes y verificación de hash determinista
        try:
            raw_bytes = self.datasets.read(proj_uuid, dataset_id)
        except (DatasetNotFound, DatasetStorageError, FileNotFoundError, OSError) as exc:
            raise ResearchInputError(
                "dataset_inaccessible",
                "El dataset no está disponible en el almacenamiento.",
            ) from exc

        if len(raw_bytes) != dataset.size:
            raise ResearchInputError(
                "dataset_incompatible",
                "El tamaño de los datos del dataset no coincide con los metadatos.",
            )

        computed_hash = compute_dataset_hash(dataset, raw_bytes)
        if computed_hash != mapping.dataset_hash:
            raise ResearchInputError(
                "dataset_hash_mismatch",
                "El hash del archivo persistido no coincide con el hash del mapeo confirmado.",
            )

        # 10. Lectura e iteración con readers existentes
        try:
            with iter_dataset(raw_bytes, dataset.format, self.datasets.limits) as parsed:
                if parsed.columns != dataset.columns:
                    raise ResearchInputError(
                        "dataset_incompatible",
                        "Las columnas del archivo no coinciden con los metadatos declarados.",
                    )
                col_indices = {c: idx for idx, c in enumerate(parsed.columns)}
                target_indices = {col_indices[c] for c in ordered_target_columns}

                extracted_rows: list[dict[str, object]] = []
                for row in parsed.rows:
                    row_dict: dict[str, object] = {}
                    for col in ordered_target_columns:
                        val = row[col_indices[col]]
                        # Detección de fórmulas no calculadas
                        if isinstance(val, str) and val.startswith("="):
                            raise ResearchInputError(
                                "dataset_uncalculated_formula",
                                "El archivo contiene fórmulas XLSX no calculadas "
                                "en columnas requeridas.",
                            )
                        # Normalizar celdas vacías o con solo espacios a None
                        if isinstance(val, str) and not val.strip():
                            val = None
                        row_dict[col] = val
                    extracted_rows.append(row_dict)

                if dataset.format == "xlsx" and target_indices.intersection(parsed.formula_columns):
                    raise ResearchInputError(
                        "dataset_uncalculated_formula",
                        "El XLSX contiene fórmulas no calculadas en columnas requeridas.",
                    )
        except InvalidDataset as exc:
            raise ResearchInputError(
                "dataset_invalid_format",
                f"El archivo del dataset no tiene una estructura válida: {exc}",
            ) from exc

        # 11. Vigencia y comprobación de cambios concurrentes tras la lectura
        try:
            post_dataset = self.datasets.get(proj_uuid, dataset_id)
        except Exception as exc:
            raise ResearchInputError(
                "dataset_concurrent_modification",
                "El dataset fue modificado o eliminado concurrentemente durante la lectura.",
            ) from exc

        if (
            post_dataset.uploaded_at != dataset.uploaded_at
            or post_dataset.size != dataset.size
            or post_dataset.columns != dataset.columns
        ):
            raise ResearchInputError(
                "dataset_concurrent_modification",
                "El dataset fue modificado concurrentemente durante la lectura.",
            )

        # Segunda comprobación del hash del dataset post-lectura
        try:
            post_raw_bytes = self.datasets.read(proj_uuid, dataset_id)
            if compute_dataset_hash(post_dataset, post_raw_bytes) != mapping.dataset_hash:
                raise ResearchInputError(
                    "dataset_concurrent_modification",
                    "El contenido del dataset fue alterado durante la lectura.",
                )
        except (DatasetNotFound, DatasetStorageError, FileNotFoundError, OSError) as exc:
            raise ResearchInputError(
                "dataset_concurrent_modification",
                "El dataset fue eliminado o se volvió inaccesible durante la lectura.",
            ) from exc

        try:
            post_context = self.reader.get_confirmed_context(str(proj_uuid), str(inst_uuid))
        except InstrumentStaleError as exc:
            code = (
                "dataset_concurrent_modification"
                if "dataset" in str(exc).lower()
                else "instrument_concurrent_modification"
            )
            raise ResearchInputError(code, str(exc)) from exc
        except Exception as exc:
            raise ResearchInputError(
                "instrument_concurrent_modification",
                "El estado del instrumento cambió durante la lectura del dataset.",
            ) from exc

        if post_context.version != context.version or post_context.updated_at != context.updated_at:
            raise ResearchInputError(
                "instrument_concurrent_modification",
                "El instrumento fue modificado concurrentemente durante la lectura del dataset.",
            )

        post_stale, post_reasons = self.instruments.check_stale(proj_uuid, inst_uuid)
        if post_stale:
            details = ", ".join(post_reasons)
            code = (
                "dataset_concurrent_modification"
                if any("dataset" in r.lower() for r in post_reasons)
                else "instrument_concurrent_modification"
            )
            raise ResearchInputError(
                code,
                f"Las fuentes quedaron desactualizadas durante la lectura: {details}",
            )

        return AuthorizedInstrumentData(
            context=context,
            rows=tuple(extracted_rows),
            column_names=tuple(ordered_target_columns),
        )


class ResearchStatisticsBridge:
    def __init__(
        self,
        projects: ProjectService,
        packages: PackageService | None = None,
        datasets: DatasetService | None = None,
        instruments: InstrumentService | None = None,
        instrument_reader: InstrumentContextReader | None = None,
    ) -> None:
        self.projects = projects
        self.packages = packages
        self.reader = PackageReaderAdapter(packages) if packages is not None else None
        self.datasets = datasets
        self.instruments = instruments
        self.instrument_bridge = (
            InstrumentStatisticsBridge(projects, datasets, instruments, instrument_reader)
            if instruments is not None and datasets is not None
            else None
        )

    def get_package(self, project_id: UUID, package_id: str) -> ResearchPackage:
        """Read only the current package in the explicitly selected project."""
        try:
            self.projects.get(project_id)
            current = self.packages.get_package(project_id)
        except ProjectNotFound as exc:
            raise ResearchInputError("project_missing", "No se encontró el proyecto.") from exc
        except (DatasetStorageError, FileNotFoundError, InvalidDataset) as exc:
            raise ResearchInputError(
                "dataset_inaccessible", "El dataset no está disponible."
            ) from exc
        except HTTPException as exc:
            if exc.status_code == 404:
                code = "package_missing"
            else:
                selected = self.packages.validate(project_id).dataset
                code = (
                    "dataset_inaccessible"
                    if selected is None
                    else "dataset_inactive"
                    if not selected.active
                    else "package_stale"
                )
            raise ResearchInputError(code, "No hay un paquete vigente para el proyecto.") from exc
        if current.id != package_id:
            raise ResearchInputError(
                "package_missing", "No hay un paquete vigente para el proyecto."
            )
        # The existing reader port is used only after checking project ownership.
        try:
            read = self.reader.get_package(package_id)
        except HTTPException as exc:
            raise ResearchInputError("package_stale", "El paquete ya no está vigente.") from exc
        except (DatasetStorageError, FileNotFoundError, InvalidDataset) as exc:
            raise ResearchInputError(
                "dataset_inaccessible", "El dataset no está disponible."
            ) from exc
        if read != current:
            raise ResearchInputError("package_stale", "El paquete ya no está vigente.")
        return read

    def read_dataset(
        self, project_id: UUID, package: ResearchPackage, reference: DatasetReference
    ) -> bytes:
        """Resolve a validated opaque key to bytes without accepting a filesystem path."""
        current = self.get_package(project_id, package.id)
        if package != current:
            raise ResearchInputError("package_stale", "El paquete ya no está vigente.")
        try:
            dataset_id = UUID(reference.id)
        except (ValueError, AttributeError) as exc:
            raise ResearchInputError(
                "invalid_reference", "La referencia del dataset no es válida."
            ) from exc
        if (
            str(dataset_id) != reference.id
            or reference.location != f"research-dataset:{dataset_id}"
            or reference.id != current.dataset.id
        ):
            raise ResearchInputError("invalid_reference", "La referencia del dataset no es válida.")
        if reference != current.dataset:
            raise ResearchInputError(
                "dataset_incompatible", "El dataset no coincide con el paquete."
            )
        try:
            dataset = self.datasets.get(project_id, dataset_id)
        except DatasetNotFound as exc:
            raise ResearchInputError(
                "dataset_inaccessible", "El dataset no está disponible."
            ) from exc
        if not dataset.active:
            raise ResearchInputError(
                "dataset_inactive", "El dataset seleccionado ya no está activo."
            )
        if (
            dataset.project_id != project_id
            or str(dataset.id) != reference.id
            or dataset.format != reference.format
            or dataset.columns != reference.columns
            or dataset.row_count != reference.row_count
            or dataset.synthetic != reference.synthetic
        ):
            raise ResearchInputError(
                "dataset_incompatible", "El dataset no coincide con el paquete."
            )
        try:
            data = self.datasets.read(project_id, dataset_id)
            preview = (
                read_csv(data, self.datasets.limits)
                if reference.format == "csv"
                else read_xlsx(data, self.datasets.limits)
            )
        except (DatasetNotFound, DatasetStorageError, FileNotFoundError, OSError) as exc:
            raise ResearchInputError(
                "dataset_inaccessible", "El dataset no está disponible."
            ) from exc
        except InvalidDataset as exc:
            raise ResearchInputError(
                "dataset_incompatible", "El dataset no coincide con el paquete."
            ) from exc
        if (
            len(data) != dataset.size
            or preview.format != reference.format
            or preview.columns != reference.columns
            or preview.row_count != reference.row_count
        ):
            raise ResearchInputError(
                "dataset_incompatible", "El dataset no coincide con el paquete."
            )
        # A second freshness check also catches source changes during the read.
        if self.get_package(project_id, package.id) != current:
            raise ResearchInputError("package_stale", "El paquete ya no está vigente.")
        return data

    def get_authorized_instrument_data(
        self,
        project_id: UUID | str,
        instrument_id: UUID | str,
        scoring_rule_id: UUID | str | None = None,
    ) -> AuthorizedInstrumentData:
        """Forward authorized instrument data request to the underlying instrument bridge."""
        if self.instrument_bridge is None:
            raise ResearchInputError(
                "bridge_unconfigured",
                "El servicio de instrumentos no está configurado en el puente de investigación.",
            )
        return self.instrument_bridge.get_authorized_instrument_data(
            project_id=project_id,
            instrument_id=instrument_id,
            scoring_rule_id=scoring_rule_id,
        )
