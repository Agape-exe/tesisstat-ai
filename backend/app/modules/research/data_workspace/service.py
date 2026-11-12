import hashlib
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal, DecimalException
from statistics import mean, median, stdev
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.modules.research.context.repository import ContextError
from app.modules.research.data_workspace.models import DictionaryPatch
from app.modules.research.datasets.readers import DatasetRows
from app.modules.research.eda.analyzer import (
    ID_NAME,
    ExploratoryAnalyzer,
    ProfilePolicy,
    missing,
    numeric,
)
from app.modules.research.preparation.engine import InvalidPlan, _missing, transform_rows
from app.modules.research.preparation.models import Operation, Plan
from app.modules.research.sources.formulas import ERROR_PREFIX
from app.modules.research.sources.repository import missing as not_found
from app.shared.analysis_v2 import Confirmation, Fact, Provenance, SourceRef, canonical_hash
from app.shared.data_sources_v2 import TableColumnV2
from app.shared.data_workspace_v2 import (
    MARKERS,
    ColumnLineageV2,
    ColumnProfileV2,
    DatasetRefV2,
    DerivedTableV2,
    FrequencyV2,
    PreparationPreviewV2,
    TableProfileV2,
    TableRecipeV2,
    VariableDictionaryV2,
    VariableV2,
)

VERSION = "table-workspace-1"
FACTS = {"name", "description", "measurement_scale", "identifier_confirmed"}
LINKS = {"column_ids", "category_order", "missing_markers"}


def fail(message, code="invalid_payload", status=422):
    raise ContextError(code, message, status)


def stable(*parts):
    return str(uuid5(NAMESPACE_URL, ":".join(parts)))


def encoded_table(names, rows):
    return json.dumps(
        {"columns": names, "rows": rows}, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def ref(kind, resource):
    return SourceRef(kind=kind, id=resource.id, revision=resource.revision, hash=resource.hash)


def storage(profile):
    if not profile["present"]:
        return "unknown"
    if profile["numeric_valid"] == profile["present"]:
        return "number"
    return "date" if profile["date_min"] else "mixed" if profile["numeric_valid"] else "string"


class WorkspaceService:
    def __init__(self, sources, repository):
        self.sources = sources
        self.repository = repository
        self.limits = sources.limits

    def publish_score(self, db, record, content):
        """C6 write port: bytes, explicit score lineage and unconfirmed dictionary."""
        self.repository.publish(db, record, content, kind="score_derived")
        dictionary = self.virtual_dictionary(record.dataset_ref)
        dictionary.revision = 1
        dictionary.updated_at = datetime.now(UTC)
        dictionary.pending_questions = ["Revisa el diccionario del derivado antes de analizarlo."]
        dictionary.hash = canonical_hash(dictionary)
        self.repository.put(
            db, record.project_id, "dictionary", record.id, dictionary.model_dump(mode="json"), 0
        )

    def derived(self, project_id, table_id):
        self.sources.require(project_id)
        value = self.repository.get(project_id, "derived", table_id)
        score = self.repository.get(project_id, "score_derived", table_id)
        if score:
            from app.shared.instruments_v2 import ScoreDerivedTableV2

            return ScoreDerivedTableV2.model_validate(score)
        if not value:
            not_found()
        return DerivedTableV2.model_validate(value)

    def dataset(self, project_id, table_id):
        self.sources.require(project_id)
        value = self.repository.get(project_id, "derived", table_id)
        if value:
            return DerivedTableV2.model_validate(value).dataset_ref
        score = self.repository.get(project_id, "score_derived", table_id)
        if score:
            return self.derived(project_id, table_id).dataset_ref
        table = self.sources.table(project_id, table_id)
        source = self.sources.repository.file(project_id, table.file_id)
        context = self.sources.context(project_id, table_id)
        sheet = next(s for s in source.sheets if s.id == table.sheet_id)
        return DatasetRefV2(
            id=table.id,
            project_id=project_id,
            hash=table.content_hash,
            kind="imported",
            name=context.name.value or f"{source.name} · {sheet.name}",
            row_count=table.row_count,
            columns=table.columns,
            source_refs=self.sources.source_refs(project_id, table_id),
        )

    def read_table(
        self, project_id, table_id, expected_revision=None, expected_hash=None, seen=None
    ):
        """Full scoped read port for S04. Validates bytes, revision and all parent evidence."""
        seen = set(seen or [])
        if table_id in seen:
            fail("El linaje contiene un ciclo.", "storage_unavailable", 503)
        seen.add(table_id)
        dataset = self.dataset(project_id, table_id)
        if expected_revision is not None and expected_revision != dataset.revision:
            fail("Cambió la revisión de la fuente.", "source_stale", 409)
        if expected_hash is not None and expected_hash != dataset.hash:
            fail("Cambió el contenido de la fuente.", "source_stale", 409)
        if dataset.kind == "imported":
            _, rows = self.sources.read_table(project_id, table_id)
        else:
            record = self.derived(project_id, table_id)
            if hasattr(record, "score_id"):
                self.score_reader.validate_derived(project_id, record)
                current = record.source_refs
            else:
                _, current = self.evidence(project_id, record.recipe, seen)
            if current != record.source_refs:
                fail(
                    "Las fuentes o su configuración cambiaron. Revisa el derivado.",
                    "source_stale",
                    409,
                )
            content = self.repository.content(project_id, table_id)
            if not content or hashlib.sha256(content).hexdigest() != dataset.hash:
                fail("El derivado está ausente o dañado.", "storage_unavailable", 503)
            payload = json.loads(content)
            if payload["columns"] != [c.name for c in dataset.columns]:
                fail("Columnas del derivado inconsistentes.", "storage_unavailable", 503)
            rows = payload["rows"]
        if len(rows) != dataset.row_count or any(len(r) != len(dataset.columns) for r in rows):
            fail("Conteos de la tabla inconsistentes.", "storage_unavailable", 503)
        return dataset, rows

    def datasets(self, project_id):
        self.sources.require(project_id)
        imported = [self.dataset(project_id, t.id) for t in self.sources.tables(project_id)]
        derived = [
            DerivedTableV2.model_validate(r).dataset_ref
            for r in self.repository.all(project_id, "derived")
        ]
        scores = [
            self.derived(project_id, r["id"]).dataset_ref
            for r in self.repository.all(project_id, "score_derived")
        ]
        return imported + derived + scores

    def virtual_dictionary(self, dataset):
        provenance = Provenance(
            kind="derived",
            source_refs=[ref("dataset", dataset)],
            algorithm_version="header-suggestion-1",
        )
        return VariableDictionaryV2(
            id=stable("dictionary", dataset.id),
            project_id=dataset.project_id,
            dataset_ref=dataset,
            hash="0" * 64,
            variables=[
                VariableV2(
                    id=stable("variable", dataset.id, c.id),
                    name=Fact(value=c.name, provenance=provenance),
                    column_ids=[c.id],
                    possible_identifier=bool(ID_NAME.search(c.name)),
                )
                for c in dataset.columns
            ],
        )

    def dictionary(self, project_id, table_id, dataset=None):
        self.history_access(project_id, table_id)
        payload = self.repository.get(project_id, "dictionary", table_id)
        if payload:
            return VariableDictionaryV2.model_validate(payload)
        dataset = dataset or self.dataset(project_id, table_id)
        result = self.virtual_dictionary(dataset)
        result.hash = canonical_hash(result)
        return result

    def history_access(self, project_id, table_id):
        self.sources.require(project_id)
        if not (
            self.repository.get(project_id, "derived", table_id)
            or self.repository.get(project_id, "score_derived", table_id)
        ):
            self.sources.table(project_id, table_id)

    def patch_dictionary(self, project_id, table_id, patch: DictionaryPatch):
        with self.repository.transaction() as db:
            dataset, rows = self.read_table(
                project_id, table_id, patch.dataset_revision, patch.dataset_hash
            )
            previous = self.dictionary(project_id, table_id, dataset)
            current = previous.model_copy(deep=True)
            current.revision += 1
            current.dataset_ref = dataset
            current.updated_at = datetime.now(UTC)
            variables = {v.id: v for v in current.variables}
            if not patch.changes and not patch.confirm_fields:
                fail("Indica campos para guardar o confirmar.")
            for variable_id, changes in patch.changes.items():
                if variable_id not in variables:
                    fail("La variable no pertenece al diccionario.")
                variable = variables[variable_id]
                for field in changes.model_fields_set:
                    value = getattr(changes, field)
                    if field in {"name", "description"} and isinstance(value, str):
                        value = value.strip() or None
                    if field in FACTS:
                        old = getattr(variable, field)
                        if value != old.value:
                            setattr(
                                variable,
                                field,
                                Fact(value=value, provenance=Provenance(kind="manual")),
                            )
                    else:
                        value = value or []
                        if field == "category_order":
                            value = [item for item in value if item.strip()]
                        if value != getattr(variable, field):
                            setattr(variable, field, value)
                            variable.field_confirmations.pop(field, None)
                            if field in {"column_ids", "category_order"}:
                                variable.measurement_scale.confirmation = None
                            if field == "column_ids":
                                variable.identifier_confirmed.confirmation = None
            for path in patch.confirm_fields:
                parts = path.split("/")
                if (
                    len(parts) != 4
                    or parts[0]
                    or parts[1] != "variables"
                    or parts[2] not in variables
                ):
                    fail("Referencia de confirmación inválida.")
                variable, field = variables[parts[2]], parts[3]
                confirmation = Confirmation(
                    actor_ref=self.sources.actor_ref,
                    confirmed_at=current.updated_at,
                    revision=current.revision,
                )
                if field in FACTS:
                    fact = getattr(variable, field)
                    if fact.value is None or fact.value in ("", "unknown"):
                        fail("Los valores desconocidos no se confirman.")
                    if (
                        field in {"measurement_scale", "identifier_confirmed"}
                        and not variable.column_ids
                    ):
                        fail("Vincula una columna antes de confirmar su interpretación.")
                    fact.confirmation = confirmation
                elif field in LINKS:
                    if field == "column_ids" and not variable.column_ids:
                        fail("Un vínculo pendiente no se confirma.")
                    variable.field_confirmations[field] = confirmation
                else:
                    fail("Campo de confirmación desconocido.")
            linked = []
            for variable in current.variables:
                if any(c not in {c.id for c in dataset.columns} for c in variable.column_ids):
                    fail("La columna no pertenece a esta tabla.")
                linked.extend(variable.column_ids)
                if len(set(variable.category_order)) != len(variable.category_order):
                    fail("No repitas categorías en el orden.")
                if (
                    variable.measurement_scale.value == "ordinal"
                    and variable.measurement_scale.confirmation
                ):
                    if not variable.category_order:
                        fail(
                            "Indica el orden explícito de categorías para confirmar una "
                            "escala ordinal."
                        )
                    column = next(c for c in dataset.columns if c.id == variable.column_ids[0])
                    observed = {
                        r[column.position]
                        for r in rows
                        if not _missing(r[column.position], variable.missing_markers, True)
                    }
                    if not observed.issubset(set(variable.category_order)):
                        fail("El orden debe incluir todas las categorías observadas no faltantes.")
            if len(set(linked)) != len(linked):
                fail("Una columna solo puede definir una variable escalar en este diccionario.")
            current.pending_questions = [
                f"{v.name.value or v.id}: vínculo pendiente"
                for v in current.variables
                if not v.column_ids
            ]
            current.hash = canonical_hash(current)
            current = VariableDictionaryV2.model_validate(current.model_dump())
            self.repository.put(
                db,
                project_id,
                "dictionary",
                table_id,
                current.model_dump(mode="json"),
                patch.expected_revision,
            )
        return current

    def configuration(self, dataset, dictionary):
        # Confirmations matter even when canonical dictionary value hash is unchanged.
        return canonical_hash(
            {
                "dataset": dataset.model_dump(mode="json"),
                "dictionary": dictionary.model_dump(mode="json"),
                "dictionary_revision": dictionary.revision,
                "engine": VERSION,
            }
        )

    def profile(self, project_id, table_id):
        self.sources.require(project_id)
        payload = self.repository.get(project_id, "profile", table_id)
        if not payload:
            not_found()
        result = TableProfileV2.model_validate(payload)
        try:
            dataset, _ = self.read_table(project_id, table_id)
            dictionary = self.dictionary(project_id, table_id, dataset)
            if result.configuration_hash != self.configuration(dataset, dictionary):
                result.state = "stale"
        except ContextError as exc:
            if exc.status != 409:
                raise
            result.state = "stale"
        return result

    def compute_profile(self, project_id, table_id, request):
        with self.repository.transaction() as db:
            dataset, rows = self.read_table(
                project_id, table_id, request.dataset_revision, request.dataset_hash
            )
            dictionary = self.dictionary(project_id, table_id, dataset)
            calculated_source = dataset.kind == "imported" and bool(
                self.sources.table(project_id, table_id).calculation_version
            )
            by_column = {c: v for v in dictionary.variables for c in v.column_ids}
            policies = {
                i: ProfilePolicy(
                    missing_markers=frozenset(
                        marker.strip().casefold() for marker in by_column[c.id].missing_markers
                    )
                )
                for i, c in enumerate(dataset.columns)
                if c.id in by_column
            }
            formulas = {
                i
                for i in range(len(dataset.columns))
                if not calculated_source
                and any(r[i] and r[i].lstrip().startswith("=") for r in rows)
            }
            analyzer = ExploratoryAnalyzer()
            raw = analyzer.analyze_rows(
                DatasetRows(
                    columns=[c.name for c in dataset.columns],
                    rows=iter(rows),
                    format="table_json",
                    formula_columns=formulas,
                ),
                policies,
            )
            columns = []
            for i, (column, item) in enumerate(zip(dataset.columns, raw["columns"], strict=True)):
                variable = by_column.get(column.id)
                scale = variable.measurement_scale.value if variable else "unknown"
                scale = scale or "unknown"
                values = [r[i] for r in rows if not missing(r[i], policies.get(i, analyzer.policy))]
                frequencies = Counter(values)
                warnings = [w["message"] for w in item["warnings"]]
                errors = sum(bool(r[i] and r[i].startswith(ERROR_PREFIX)) for r in rows)
                if errors:
                    warnings.append(
                        f"{errors} celdas con errores de Excel o fórmulas sin valor fiable. "
                        "Esta columna no está lista para analizar; corrige el original y reimporta."
                    )
                numeric_summary = None
                quantitative = (
                    variable
                    and variable.measurement_scale.confirmation
                    and scale in {"interval", "ratio"}
                    and variable.identifier_confirmed.value is not True
                )
                if quantitative and values and all(numeric(v) is not None for v in values):
                    numbers = [Decimal(v.strip()) for v in values]
                    try:
                        if any(
                            abs(n.adjusted()) > 308 or len(n.as_tuple().digits) > 1000
                            for n in numbers
                        ):
                            raise ValueError("Exploratory summary range exceeded")
                        numeric_summary = {
                            "min": str(min(numbers)),
                            "max": str(max(numbers)),
                            "mean": str(mean(numbers)),
                            "median": str(median(numbers)),
                        }
                        if len(numbers) > 1:
                            numeric_summary["sample_stdev"] = str(stdev(numbers))
                    except (DecimalException, OverflowError, ValueError):
                        numeric_summary = None
                        warnings.append("Resumen no calculable: valores fuera del rango admitido.")
                elif scale in {"unknown", "nominal", "ordinal"}:
                    warnings.append(
                        "Frecuencias sobre presentes; no se promedian códigos ni escalas "
                        "sin confirmar."
                    )
                columns.append(
                    ColumnProfileV2(
                        column_id=column.id,
                        name=column.name,
                        storage_type=storage(item),
                        measurement_scale=scale,
                        present=item["present"],
                        missing=item["missing"],
                        distinct=item["distinct"],
                        constant=item["constant"],
                        possible_identifier=item["possible_identifier"],
                        formula_count=column.formula_count
                        if calculated_source
                        else sum(bool(r[i] and r[i].lstrip().startswith("=")) for r in rows),
                        frequencies=[
                            FrequencyV2(
                                value=value, count=count, percentage=100 * count / len(values)
                            )
                            for value, count in sorted(
                                frequencies.items(), key=lambda x: (-x[1], x[0])
                            )[:10]
                        ],
                        numeric_summary=numeric_summary,
                        warnings=warnings,
                    )
                )
            previous = self.repository.get(project_id, "profile", table_id, db)
            summary = raw["summary"]
            result = TableProfileV2(
                id=stable("profile", table_id),
                project_id=project_id,
                revision=previous["revision"] + 1 if previous else 1,
                hash="0" * 64,
                dataset_ref=dataset,
                dictionary_ref=ref("dictionary", dictionary) if dictionary.revision else None,
                source_refs=dataset.source_refs,
                configuration_hash=self.configuration(dataset, dictionary),
                engine_version=f"{VERSION}/{analyzer.version}",
                formula_policy="calculated-subset-cache-ignored"
                if calculated_source
                else "text-no-evaluation",
                missing_policy={
                    c.id: by_column[c.id].missing_markers if c.id in by_column else MARKERS
                    for c in dataset.columns
                },
                created_at=datetime.now(UTC),
                rows=len(rows),
                columns_count=len(dataset.columns),
                missing=summary["missing"],
                duplicates=summary["duplicates"],
                constant_columns=summary["constant_columns"],
                empty_columns=summary["empty_columns"],
                columns=columns,
                warnings=[
                    "Las advertencias no modifican datos. Un duplicado puede ser legítimo.",
                    "Las fórmulas nuevas usan cálculo acotado sin caché; las importaciones "
                    "históricas conservan su política. Los errores requieren corregir y reimportar."
                    " No se realizan pruebas inferenciales.",
                ],
            )
            result.hash = canonical_hash(result)
            self.repository.put(
                db,
                project_id,
                "profile",
                table_id,
                result.model_dump(mode="json"),
                previous["revision"] if previous else 0,
            )
        return result

    def evidence(self, project_id, recipe, seen=None):
        ids = [recipe.left_table_id]
        if recipe.kind == "join":
            if not recipe.right_table_id or recipe.right_table_id == recipe.left_table_id:
                fail("Elige dos tablas distintas del mismo proyecto.")
            ids.append(recipe.right_table_id)
        tables, refs = {}, []
        for table_id in ids:
            dataset, rows = self.read_table(project_id, table_id, seen=seen)
            tables[table_id] = (dataset, rows)
            refs += [ref("dataset", dataset), *dataset.source_refs]
            dictionary = self.dictionary(project_id, table_id, dataset)
            if dictionary.revision:
                refs.append(ref("dictionary", dictionary))
        # Preserve ordering and deduplicate parents shared by tables in the same workbook.
        unique = {(r.kind, r.id, r.revision, r.hash): r for r in refs}
        return tables, list(unique.values())

    def _markers(self, project_id, dataset, column_id):
        dictionary = self.dictionary(project_id, dataset.id, dataset)
        return next(
            (v.missing_markers for v in dictionary.variables if column_id in v.column_ids), MARKERS
        )

    def build(self, project_id, recipe):
        tables, refs = self.evidence(project_id, recipe)
        left, left_rows = tables[recipe.left_table_id]
        counts = {"left_rows": len(left_rows)}
        warnings, blockers = [], []
        unmatched_left, unmatched_right = [], []
        if recipe.kind == "join":
            if recipe.operations or not recipe.columns or not recipe.unmatched_policy:
                fail("Elige columnas y una política explícita de casos sin pareja.")
            right, right_rows = tables[recipe.right_table_id]
            counts["right_rows"] = len(right_rows)

            def keys(dataset, rows, key):
                if key not in {c.id for c in dataset.columns}:
                    fail("La clave debe ser una columna de su tabla.")
                index = next(c.position for c in dataset.columns if c.id == key)
                markers = self._markers(project_id, dataset, key)
                found, absent, duplicates = {}, [], 0
                for number, row in enumerate(rows, 1):
                    value = row[index]
                    if _missing(value, markers, True):
                        absent.append(number)
                    elif value in found:
                        duplicates += 1
                    else:
                        found[value] = number
                return found, absent, duplicates

            lk, lm, ld = keys(left, left_rows, recipe.left_key)
            rk, rm, rd = keys(right, right_rows, recipe.right_key)
            matches = lk.keys() & rk.keys()
            unmatched_left = sorted([lk[k] for k in lk.keys() - rk.keys()] + lm)
            unmatched_right = sorted([rk[k] for k in rk.keys() - lk.keys()] + rm)
            counts |= {
                "matches": len(matches),
                "left_only": len(lk.keys() - rk.keys()),
                "right_only": len(rk.keys() - lk.keys()),
                "left_missing_keys": len(lm),
                "right_missing_keys": len(rm),
                "left_duplicate_keys": ld,
                "right_duplicate_keys": rd,
            }
            if ld or rd:
                blockers.append(
                    "Hay claves duplicadas. Resuélvelas antes de una combinación uno "
                    "a uno; no se agregan ni eliminan automáticamente."
                )
            pairs = [(i, rk[k]) for k, i in lk.items() if k in matches]
            if recipe.unmatched_policy == "all_cases":
                pairs += [(i, None) for i in unmatched_left] + [(None, i) for i in unmatched_right]
            # A blocked preview never claims a usable result from arbitrarily chosen duplicates.
            if blockers:
                pairs = []
            output, lineage = [], []
            for column in recipe.columns:
                if column.table_id not in tables:
                    fail("La columna de salida pertenece a otra tabla.")
                dataset = tables[column.table_id][0]
                match = next((c for c in dataset.columns if c.id == column.column_id), None)
                if match is None:
                    fail("La columna de salida no existe.")
                output.append((column.table_id, match.position, column.name))
            if len({c[2] for c in output}) != len(output):
                fail("Los nombres de salida deben ser únicos; resuelve las colisiones.")
            rows = []
            for li, ri in pairs:
                source_indices = {left.id: li, right.id: ri}
                rows.append(
                    [
                        tables[tid][1][source_indices[tid] - 1][pos]
                        if source_indices[tid] is not None
                        else None
                        for tid, pos, _ in output
                    ]
                )
                lineage.append(source_indices)
            names = [c[2] for c in output]
            column_sources = [(c.table_id, c.column_id) for c in recipe.columns]
            warnings += [
                "Claves: texto exacto, sensible a mayúsculas y espacios; 001 es "
                "distinto de 1. Solo los faltantes usan trim/casefold del diccionario.",
                "Las claves faltantes nunca se emparejan. Las ausencias quedan "
                "como null, nunca cero.",
                "Combinar no confirma población, diseño, causalidad ni mejora.",
            ]
        else:
            if (
                recipe.columns
                or recipe.right_table_id
                or recipe.left_key
                or recipe.right_key
                or recipe.unmatched_policy
            ):
                fail("Una preparación usa una tabla y operaciones explícitas.")
            if not recipe.operations:
                fail("Indica al menos una operación de preparación.")
            names = [c.name for c in left.columns]
            rows = [r.copy() for r in left_rows]
            column_sources = [(left.id, c.id) for c in left.columns]
            lineage = [{left.id: i} for i in range(1, len(rows) + 1)]
            for op in recipe.operations:
                if len(set(op.column_ids)) != len(op.column_ids):
                    fail("No repitas columnas en una operación.")
                selected = [c for c in left.columns if c.id in op.column_ids]
                if len(selected) != len(op.column_ids):
                    fail("La operación contiene columnas ajenas.")
                if op.type == "drop_duplicates":
                    if op.column_ids or op.new_name is not None or op.value is not None:
                        fail(
                            "Eliminar duplicados compara filas completas y no recibe columnas "
                            "ni valores."
                        )
                    seen, keep = set(), []
                    for i, row in enumerate(rows):
                        if tuple(row) not in seen:
                            keep.append(i)
                            seen.add(tuple(row))
                    rows, lineage = [rows[i] for i in keep], [lineage[i] for i in keep]
                    continue
                if not op.column_ids or (
                    op.type in {"rename_column", "replace_missing"} and len(selected) != 1
                ):
                    fail("Selecciona las columnas necesarias para la operación.")
                positions = []
                for column in selected:
                    pair = (left.id, column.id)
                    if pair not in column_sources:
                        fail("Una columna utilizada ya fue eliminada.")
                    positions.append(column_sources.index(pair))
                if op.type == "drop_missing":
                    keep = [
                        i
                        for i, row in enumerate(rows)
                        if not any(
                            _missing(row[pos], self._markers(project_id, left, column.id), True)
                            for column, pos in zip(selected, positions, strict=True)
                        )
                    ]
                    rows, lineage = [rows[i] for i in keep], [lineage[i] for i in keep]
                else:
                    # Adapt real IDs to the existing engine; names are never matched by similarity.
                    operation = Operation(
                        type=op.type,
                        columns=[names[i] for i in positions],
                        column=names[positions[0]],
                        new_name=op.new_name,
                        value=op.value,
                    )
                    if op.type == "replace_missing":
                        if op.value is None:
                            fail("Indica un valor explícito de reemplazo.")
                        markers = self._markers(project_id, left, selected[0].id)
                        pos = positions[0]
                        for row in rows:
                            if _missing(row[pos], markers, True):
                                row[pos] = op.value
                    else:
                        try:
                            result = transform_rows(names, rows, Plan(operations=[operation]))
                        except InvalidPlan as exc:
                            fail(str(exc))
                        names, rows = result["columns"], result["rows"]
                        warnings += result["warnings"]
                        if op.type == "drop_columns":
                            column_sources = [
                                c for i, c in enumerate(column_sources) if i not in positions
                            ]
            counts["rows_removed"] = len(left_rows) - len(rows)
        if len(rows) > self.limits.max_rows or len(names) > self.limits.max_columns:
            fail("El resultado supera los límites de filas o columnas.", "limit_exceeded", 413)
        data = encoded_table(names, rows)
        if len(data) > self.limits.max_bytes:
            fail(
                "El resultado supera el límite de bytes de la tabla (10 MiB).",
                "limit_exceeded",
                413,
            )
        counts |= {"result_rows": len(rows), "result_columns": len(names)}
        if recipe.kind == "prepare":
            positions = {c.id: c.position for c in left.columns}
            counts["cells_changed"] = sum(
                row[i] != left_rows[lineage[n][left.id] - 1][positions[cid]]
                for n, row in enumerate(rows)
                for i, (_, cid) in enumerate(column_sources)
            )
        return dict(
            tables=tables,
            refs=refs,
            names=names,
            rows=rows,
            data=data,
            lineage=lineage,
            column_sources=column_sources,
            counts=counts,
            warnings=warnings,
            blockers=blockers,
            unmatched_left=unmatched_left,
            unmatched_right=unmatched_right,
        )

    def preview(self, project_id, recipe: TableRecipeV2):
        with self.repository.transaction() as db:
            result = self.build(project_id, recipe)
            now = datetime.now(UTC)
            preview = PreparationPreviewV2(
                id=str(uuid4()),
                project_id=project_id,
                recipe=recipe,
                recipe_hash=canonical_hash(recipe),
                source_refs=result["refs"],
                configuration_hash=canonical_hash(
                    [r.model_dump(mode="json") for r in result["refs"]]
                ),
                result_hash=hashlib.sha256(result["data"]).hexdigest(),
                engine_version=VERSION,
                created_at=now,
                expires_at=now + timedelta(minutes=30),
                counts=result["counts"],
                result_columns=result["names"],
                rows=result["rows"][:20],
                unmatched_left=result["unmatched_left"],
                unmatched_right=result["unmatched_right"],
                unmatched_left_rows=[
                    result["tables"][recipe.left_table_id][1][i - 1]
                    for i in result["unmatched_left"][:20]
                ],
                unmatched_right_rows=[
                    result["tables"][recipe.right_table_id][1][i - 1]
                    for i in result["unmatched_right"][:20]
                ],
                warnings=result["warnings"],
                blockers=result["blockers"],
            )
            self.repository.put(
                db,
                project_id,
                "preview",
                preview.id,
                preview.model_dump(mode="json") | {"revision": 1},
                0,
            )
        return preview

    def apply(self, project_id, request):
        self.sources.require(project_id)
        with self.repository.transaction() as db:
            payload = self.repository.get(project_id, "preview", request.preview_id, db)
            if payload is None:
                not_found()
            payload.pop("revision")
            preview = PreparationPreviewV2.model_validate(payload)
            if request.recipe_hash != preview.recipe_hash:
                fail("La receta no coincide con la vista previa.", "source_stale", 409)
            existing = self.repository.applied(db, project_id, preview.id)
            if existing:
                record = DerivedTableV2.model_validate(existing)
                content = self.repository.content(project_id, record.id)
                if not content or hashlib.sha256(content).hexdigest() != record.dataset_ref.hash:
                    fail("El derivado publicado está ausente o dañado.", "storage_unavailable", 503)
                return record
            if preview.expires_at <= datetime.now(UTC) or preview.engine_version != VERSION:
                fail("La vista previa venció. Genera una nueva.", "source_stale", 409)
            result = self.build(project_id, preview.recipe)
            if (
                result["refs"] != preview.source_refs
                or hashlib.sha256(result["data"]).hexdigest() != preview.result_hash
            ):
                fail(
                    "Las fuentes o su configuración cambiaron. Genera otra vista previa.",
                    "source_stale",
                    409,
                )
            if result["blockers"]:
                fail("Resuelve las claves duplicadas antes de combinar.", "source_stale", 409)
            now, table_id = datetime.now(UTC), str(uuid4())
            columns = [
                TableColumnV2(
                    id=str(uuid4()),
                    name=name,
                    position=i,
                    formula_error_count=sum(
                        bool(r[i] and r[i].startswith(ERROR_PREFIX)) for r in result["rows"]
                    ),
                )
                for i, name in enumerate(result["names"])
            ]
            lineage = [
                ColumnLineageV2(
                    source_table_id=tid, source_column_id=cid, result_column_id=column.id
                )
                for (tid, cid), column in zip(result["column_sources"], columns, strict=True)
            ]
            for tid, (source, _) in result["tables"].items():
                lineage += [
                    ColumnLineageV2(
                        source_table_id=tid, source_column_id=c.id, result_column_id=None
                    )
                    for c in source.columns
                    if (tid, c.id) not in result["column_sources"]
                ]
            declarations = [dataset.synthetic for dataset, _ in result["tables"].values()]
            synthetic = (
                False
                if False in declarations
                else True
                if all(v is True for v in declarations)
                else None
            )
            dataset = DatasetRefV2(
                id=table_id,
                project_id=project_id,
                hash=preview.result_hash,
                kind="derived",
                name=preview.recipe.name,
                row_count=len(result["rows"]),
                columns=columns,
                synthetic=synthetic,
                source_refs=preview.source_refs,
            )
            record = DerivedTableV2(
                id=table_id,
                project_id=project_id,
                hash="0" * 64,
                dataset_ref=dataset,
                preview_id=preview.id,
                recipe=preview.recipe,
                source_refs=preview.source_refs,
                created_at=now,
                confirmation=Confirmation(
                    actor_ref=self.sources.actor_ref, confirmed_at=now, revision=1
                ),
                engine_version=VERSION,
                counts=result["counts"],
                column_lineage=lineage,
                row_lineage=result["lineage"],
                warnings=result["warnings"],
            )
            # The preparation reference identifies the immutable recipe, not its enclosing record.
            dataset.preparation_ref = SourceRef(
                kind="preparation", id=record.id, revision=1, hash=preview.recipe_hash
            )
            record.hash = canonical_hash(record)
            dictionary = self.virtual_dictionary(dataset)
            dictionary.variables = []
            for tid, (parent, _) in result["tables"].items():
                original = self.dictionary(project_id, tid, parent)
                for variable in original.variables:
                    copied = variable.model_copy(deep=True)
                    copied.id = str(uuid4())
                    copied.column_ids = [
                        link.result_column_id
                        for link in lineage
                        if link.source_table_id == tid
                        and link.source_column_id in variable.column_ids
                        and link.result_column_id is not None
                    ]
                    # A join projects chosen columns. Omitted definitions remain in their
                    # referenced source dictionaries; they are not statistical variables
                    # of this result merely because their keys helped match the rows.
                    if preview.recipe.kind == "join" and not copied.column_ids:
                        continue
                    for field in FACTS:
                        fact = getattr(copied, field)
                        fact.confirmation = None
                        fact.provenance = Provenance(
                            kind="derived",
                            source_refs=preview.source_refs,
                            algorithm_version=VERSION,
                        )
                    copied.field_confirmations = {}
                    dictionary.variables.append(copied)
            # A join can carry more definitions than output columns; keep dropped links pending.
            if len(dictionary.variables) > 200:
                fail(
                    "El diccionario derivado supera 200 definiciones; reduce las fuentes.",
                    "limit_exceeded",
                    413,
                )
            dictionary.revision, dictionary.updated_at = 1, now
            dictionary.pending_questions = [
                f"{v.name.value}: revisa el vínculo y la interpretación del derivado."
                for v in dictionary.variables
            ]
            dictionary.hash = canonical_hash(dictionary)
            self.repository.publish(db, record, result["data"])
            self.repository.put(
                db, project_id, "dictionary", table_id, dictionary.model_dump(mode="json"), 0
            )
        return record

    def summary(self, project_id):
        datasets = self.datasets(project_id)
        items = []
        for dataset in datasets:
            dictionary = self.dictionary(project_id, dataset.id, dataset)
            profile = self.repository.get(project_id, "profile", dataset.id)
            state = self.profile(project_id, dataset.id).state if profile else "absent"
            usable = True
            try:
                self.read_table(project_id, dataset.id)
            except ContextError as exc:
                if exc.status != 409:
                    raise
                usable = False
            confirmed = sum(
                bool(
                    v.name.confirmation
                    and v.measurement_scale.confirmation
                    and v.field_confirmations.get("column_ids")
                )
                for v in dictionary.variables
            )
            items.append(
                {
                    "id": dataset.id,
                    "name": dataset.name,
                    "kind": dataset.kind,
                    "profile": state,
                    "variables": len(dictionary.variables),
                    "confirmed_variables": confirmed,
                    "usable": usable,
                }
            )
        return {"tables": items, "derived": sum(d.kind == "derived" for d in datasets)}
