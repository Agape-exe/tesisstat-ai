"""Synthetic fixtures for InstrumentContext v1.0.0 testing and validation."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.modules.research.instrument.contracts import InstrumentContext
from app.modules.research.instrument.models import (
    DatasetMapping,
    InstrumentConfirmation,
    InstrumentDimension,
    InstrumentIndicator,
    InstrumentItem,
    InstrumentProvenance,
    InstrumentVariable,
    ItemColumnMapping,
    ResponseOption,
    ScoringRule,
)


def standard_likert_options() -> list[ResponseOption]:
    return [
        ResponseOption(code="1", label="Totalmente en desacuerdo", numeric_value=1.0),
        ResponseOption(code="2", label="En desacuerdo", numeric_value=2.0),
        ResponseOption(code="3", label="Neutral", numeric_value=3.0),
        ResponseOption(code="4", label="De acuerdo", numeric_value=4.0),
        ResponseOption(code="5", label="Totalmente de acuerdo", numeric_value=5.0),
    ]


# Fixture 1: Instrumento válido confirmado con dos ítems, uno de ellos invertido
def make_valid_confirmed_instrument() -> InstrumentContext:
    var_id = uuid4()
    dim_id = uuid4()
    ind_id = uuid4()
    item1_id = uuid4()
    item2_id = uuid4()
    rule_id = uuid4()
    inst_id = uuid4()
    dataset_id = uuid4()
    created = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
    confirmed_dt = datetime(2026, 11, 2, 12, 30, tzinfo=UTC)
    updated = confirmed_dt

    return InstrumentContext(
        schema_version="1.0.0",
        instrument_id=inst_id,
        project_id=uuid4(),
        version=1,
        status="reviewed",
        created_at=created,
        updated_at=updated,
        provenance=InstrumentProvenance(
            source_kind="document",
            source_document_id=uuid4(),
            source_document_hash="a" * 64,
            methodology_review_id=uuid4(),
            methodology_review_version=1,
            methodology_review_hash="b" * 64,
        ),
        confirmation=InstrumentConfirmation(
            state="confirmed",
            confirmed_at=confirmed_dt,
            confirmer_ref="revisor_metodologico",
        ),
        variables=[
            InstrumentVariable(
                variable_id=var_id,
                name="Clima Laboral",
                scale="ordinal",
                methodology_variable_id=uuid4(),
            )
        ],
        dimensions=[
            InstrumentDimension(
                dimension_id=dim_id,
                variable_id=var_id,
                name="Comunicación Interna",
            )
        ],
        indicators=[
            InstrumentIndicator(
                indicator_id=ind_id,
                dimension_id=dim_id,
                name="Claridad de Información",
            )
        ],
        items=[
            InstrumentItem(
                item_id=item1_id,
                variable_id=var_id,
                dimension_id=dim_id,
                indicator_id=ind_id,
                text="La comunicación de la dirección es oportuna y clara.",
                response_type="single_choice",
                response_options=standard_likert_options(),
                valid_min=1.0,
                valid_max=5.0,
                reverse_scored=False,
            ),
            InstrumentItem(
                item_id=item2_id,
                variable_id=var_id,
                dimension_id=dim_id,
                indicator_id=ind_id,
                text="Frecuentemente recibo información contradictoria de mis superiores.",
                response_type="single_choice",
                response_options=standard_likert_options(),
                valid_min=1.0,
                valid_max=5.0,
                reverse_scored=True,
                reverse_rule="min_plus_max_minus_value",
            ),
        ],
        scoring_rules=[
            ScoringRule(
                scoring_rule_id=rule_id,
                scope="dimension",
                dimension_id=dim_id,
                item_ids=[item1_id, item2_id],
                aggregation="sum",
                missing_policy="all_required",
                confirmed=True,
            )
        ],
        dataset_mapping=DatasetMapping(
            dataset_id=dataset_id,
            dataset_hash="c" * 64,
            instrument_version=1,
            item_columns=[
                ItemColumnMapping(item_id=item1_id, column_name="p1_comunicacion_directa"),
                ItemColumnMapping(item_id=item2_id, column_name="p2_info_contradictoria"),
            ],
            status="confirmed",
            confirmation=InstrumentConfirmation(
                state="confirmed",
                confirmed_at=confirmed_dt,
                confirmer_ref="revisor_metodologico",
            ),
        ),
    )


# Fixture 2: Ítem invertido sin rango válido declarado
def make_inverted_item_without_range() -> dict:
    return {
        "item_id": uuid4(),
        "variable_id": uuid4(),
        "dimension_id": uuid4(),
        "indicator_id": uuid4(),
        "text": "Ítem invertido sin rango declarado.",
        "response_type": "single_choice",
        "response_options": standard_likert_options(),
        "valid_min": None,
        "valid_max": None,
        "reverse_scored": True,
        "reverse_rule": "min_plus_max_minus_value",
    }


# Fixture 3: Alternativas de respuesta con códigos duplicados
def make_duplicate_response_options() -> dict:
    return {
        "item_id": uuid4(),
        "variable_id": uuid4(),
        "dimension_id": uuid4(),
        "indicator_id": uuid4(),
        "text": "Ítem con opciones duplicadas.",
        "response_type": "single_choice",
        "response_options": [
            ResponseOption(code="A", label="Opción 1", numeric_value=1.0),
            ResponseOption(code="A", label="Opción 2", numeric_value=2.0),
        ],
    }


# Fixture 4: Referencias jerárquicas inválidas (dimensión no pertenece a la variable)
def make_invalid_hierarchy_references() -> tuple[
    list[InstrumentVariable],
    list[InstrumentDimension],
    list[InstrumentIndicator],
    list[InstrumentItem],
]:
    var1_id = uuid4()
    var2_id = uuid4()
    dim1_id = uuid4()
    ind1_id = uuid4()

    variables = [
        InstrumentVariable(variable_id=var1_id, name="Variable 1"),
        InstrumentVariable(variable_id=var2_id, name="Variable 2"),
    ]
    dimensions = [
        InstrumentDimension(dimension_id=dim1_id, variable_id=var1_id, name="Dimensión 1"),
    ]
    indicators = [
        InstrumentIndicator(indicator_id=ind1_id, dimension_id=dim1_id, name="Indicador 1"),
    ]
    items = [
        InstrumentItem(
            item_id=uuid4(),
            variable_id=var2_id,  # Discrepancia intencional con dim1 (pertenece a var1)
            dimension_id=dim1_id,
            indicator_id=ind1_id,
            text="Pregunta con jerarquía desalineada.",
            response_type="numeric",
            valid_min=0.0,
            valid_max=10.0,
        )
    ]
    return variables, dimensions, indicators, items


# Fixture 5: Regla de puntuación que mezcla dimensiones o apunta a un target inexistente
def make_cross_dimensional_scoring_rule(
    valid_instrument: InstrumentContext,
) -> ScoringRule:
    fake_dim_id = uuid4()  # No existe en el instrumento
    return ScoringRule(
        scoring_rule_id=uuid4(),
        scope="dimension",
        dimension_id=fake_dim_id,
        item_ids=[valid_instrument.items[0].item_id],
        aggregation="mean",
        missing_policy="all_required",
        confirmed=True,
    )


# Fixture 6: Mapeo incompleto confirmado (falta cubrir un ítem)
def make_incomplete_mapping_confirmed(
    valid_instrument: InstrumentContext,
) -> DatasetMapping:
    # Solo mapea el primer ítem, dejando el segundo fuera
    first_item = valid_instrument.items[0]
    return DatasetMapping(
        dataset_id=uuid4(),
        dataset_hash="d" * 64,
        instrument_version=valid_instrument.version,
        item_columns=[
            ItemColumnMapping(item_id=first_item.item_id, column_name="columna_1"),
        ],
        status="confirmed",
        confirmation=InstrumentConfirmation(
            state="confirmed",
            confirmed_at=datetime.now(UTC),
            confirmer_ref="revisor",
        ),
    )


# Fixture 7: Columna de dataset duplicada en dos ítems
def make_duplicate_column_mapping(item1_id: UUID, item2_id: UUID) -> dict:
    return {
        "dataset_id": uuid4(),
        "dataset_hash": "e" * 64,
        "instrument_version": 1,
        "item_columns": [
            ItemColumnMapping(item_id=item1_id, column_name="columna_compartida"),
            ItemColumnMapping(item_id=item2_id, column_name="columna_compartida"),
        ],
        "status": "draft",
    }


# Fixture 8: Mapeo marcado como confirmado pero sin confirmación humana explícita
def make_confirmed_mapping_unauthorized(item_id: UUID) -> dict:
    return {
        "dataset_id": uuid4(),
        "dataset_hash": "f" * 64,
        "instrument_version": 1,
        "item_columns": [
            ItemColumnMapping(item_id=item_id, column_name="columna_valida"),
        ],
        "status": "confirmed",
        "confirmation": InstrumentConfirmation(state="pending"),
    }


# Fixture 9: Versión de instrumento incompatible en el mapeo
def make_incompatible_instrument_version(
    valid_instrument: InstrumentContext,
) -> DatasetMapping:
    return DatasetMapping(
        dataset_id=uuid4(),
        dataset_hash="a" * 64,
        instrument_version=valid_instrument.version + 99,  # Incompatible
        item_columns=[
            ItemColumnMapping(item_id=it.item_id, column_name=f"col_{i}")
            for i, it in enumerate(valid_instrument.items)
        ],
        status="draft",
    )


# Fixture 10: Instrumento válido revisado sin dataset asociado
def make_valid_reviewed_without_dataset() -> InstrumentContext:
    var_id = uuid4()
    dim_id = uuid4()
    ind_id = uuid4()
    item_id = uuid4()
    rule_id = uuid4()
    created = datetime(2026, 11, 3, 8, 0, tzinfo=UTC)
    confirmed_dt = datetime(2026, 11, 3, 9, 15, tzinfo=UTC)
    updated = confirmed_dt

    return InstrumentContext(
        schema_version="1.0.0",
        instrument_id=uuid4(),
        project_id=uuid4(),
        version=1,
        status="reviewed",
        created_at=created,
        updated_at=updated,
        provenance=InstrumentProvenance(
            source_kind="manual",
            methodology_review_id=uuid4(),
            methodology_review_version=1,
            methodology_review_hash="d" * 64,
        ),
        confirmation=InstrumentConfirmation(
            state="confirmed",
            confirmed_at=confirmed_dt,
            confirmer_ref="auditor_investigacion",
        ),
        variables=[
            InstrumentVariable(
                variable_id=var_id,
                name="Autoeficacia",
                scale="interval",
                methodology_variable_id=uuid4(),
            )
        ],
        dimensions=[
            InstrumentDimension(
                dimension_id=dim_id,
                variable_id=var_id,
                name="Confianza en Tareas Complejas",
            )
        ],
        indicators=[
            InstrumentIndicator(
                indicator_id=ind_id,
                dimension_id=dim_id,
                name="Persistencia",
            )
        ],
        items=[
            InstrumentItem(
                item_id=item_id,
                variable_id=var_id,
                dimension_id=dim_id,
                indicator_id=ind_id,
                text="Puedo resolver problemas difíciles si me esfuerzo lo suficiente.",
                response_type="single_choice",
                response_options=standard_likert_options(),
                valid_min=1.0,
                valid_max=5.0,
                reverse_scored=False,
            )
        ],
        scoring_rules=[
            ScoringRule(
                scoring_rule_id=rule_id,
                scope="dimension",
                dimension_id=dim_id,
                item_ids=[item_id],
                aggregation="mean",
                missing_policy="all_required",
                confirmed=True,
            )
        ],
        dataset_mapping=None,
    )
