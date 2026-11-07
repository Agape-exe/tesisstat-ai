"""Comprehensive tests for InstrumentContext v1.0.0 domain models and validations."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.research.instrument.contracts import InstrumentContext
from app.modules.research.instrument.fixtures import (
    make_confirmed_mapping_unauthorized,
    make_cross_dimensional_scoring_rule,
    make_duplicate_column_mapping,
    make_duplicate_response_options,
    make_incompatible_instrument_version,
    make_incomplete_mapping_confirmed,
    make_invalid_hierarchy_references,
    make_inverted_item_without_range,
    make_valid_confirmed_instrument,
    make_valid_reviewed_without_dataset,
    standard_likert_options,
)
from app.modules.research.instrument.models import (
    DatasetMapping,
    InstrumentConfirmation,
    InstrumentDimension,
    InstrumentItem,
    InstrumentProvenance,
    ItemColumnMapping,
    ResponseOption,
    ScoringRule,
    is_pii_column,
)
from app.shared.contracts import (
    AnalysisPlan,
    AnalysisResult,
    DatasetReference,
    ResearchHypothesis,
    ResearchPackage,
    ResearchVariable,
)


def _with_updates(inst: InstrumentContext, **updates) -> InstrumentContext:
    dumped = inst.model_dump()
    dumped.update(updates)
    return InstrumentContext.model_validate(dumped)


class TestInstrumentContextModels:
    def test_fixture_1_valid_confirmed_instrument(self):
        """Fixture 1: Instrumento válido confirmado con dos ítems (uno invertido)."""
        inst = make_valid_confirmed_instrument()
        assert inst.schema_version == "1.0.0"
        assert inst.status == "reviewed"
        assert inst.confirmation.state == "confirmed"
        assert len(inst.items) == 2
        assert inst.items[0].item_id is not None
        assert inst.items[1].reverse_scored is True
        assert inst.items[1].reverse_rule == "min_plus_max_minus_value"
        assert inst.scoring_rules[0].scoring_rule_id is not None
        assert inst.scoring_rules[0].scope == "dimension"
        assert inst.dataset_mapping is not None
        assert inst.dataset_mapping.status == "confirmed"
        assert inst.dataset_mapping.confirmation.state == "confirmed"

    def test_fixture_2_inverted_item_without_range_fails(self):
        """Fixture 2: Ítem invertido sin rango válido declarado es rechazado."""
        data = make_inverted_item_without_range()
        with pytest.raises(ValidationError) as exc:
            InstrumentItem.model_validate(data)
        assert "valid_min y valid_max" in str(exc.value)

    def test_fixture_3_duplicate_response_options_fails(self):
        """Fixture 3: Alternativas de respuesta con códigos duplicados son rechazadas."""
        data = make_duplicate_response_options()
        with pytest.raises(ValidationError) as exc:
            InstrumentItem.model_validate(data)
        assert "códigos únicos" in str(exc.value)

    def test_fixture_4_invalid_hierarchy_references_fails(self):
        """Fixture 4: Ítem con desalineación jerárquica variable-dimensión es rechazado."""
        vars_, dims, inds, items = make_invalid_hierarchy_references()
        now = datetime.now(UTC)
        with pytest.raises(ValidationError) as exc:
            InstrumentContext(
                instrument_id=uuid4(),
                project_id=uuid4(),
                created_at=now,
                updated_at=now,
                variables=vars_,
                dimensions=dims,
                indicators=inds,
                items=items,
            )
        assert "Inconsistencia jerárquica" in str(exc.value)

    def test_fixture_5_cross_dimensional_scoring_rule_fails(self):
        """Fixture 5: Regla de puntuación que referencia una dimensión inexistente es rechazada."""
        inst = make_valid_confirmed_instrument()
        bad_rule = make_cross_dimensional_scoring_rule(inst)
        with pytest.raises(ValidationError) as exc:
            _with_updates(inst, scoring_rules=[bad_rule])
        assert "apunta a una dimensión inexistente" in str(exc.value)

    def test_fixture_6_incomplete_mapping_confirmed_fails(self):
        """Fixture 6: Mapeo confirmado sin cubrir el 100% de ítems es rechazado."""
        inst = make_valid_confirmed_instrument()
        incomplete_mapping = make_incomplete_mapping_confirmed(inst)
        with pytest.raises(ValidationError) as exc:
            _with_updates(inst, dataset_mapping=incomplete_mapping)
        assert "debe cubrir todos los ítems" in str(exc.value)

    def test_fixture_7_duplicate_column_mapping_fails(self):
        """Fixture 7: Dos ítems asignados a la misma columna de dataset son rechazados."""
        data = make_duplicate_column_mapping(uuid4(), uuid4())
        with pytest.raises(ValidationError) as exc:
            DatasetMapping.model_validate(data)
        assert "No se permite vincular una columna con varios ítems" in str(exc.value)

    def test_fixture_8_confirmed_mapping_unauthorized_fails(self):
        """Fixture 8: Mapeo status='confirmed' sin confirmación humana explícita es rechazado."""
        data = make_confirmed_mapping_unauthorized(uuid4())
        with pytest.raises(ValidationError) as exc:
            DatasetMapping.model_validate(data)
        assert "confirmation.state='confirmed'" in str(exc.value)

    def test_fixture_9_incompatible_instrument_version_fails(self):
        """Fixture 9: Mapeo con instrument_version discordante es rechazado."""
        inst = make_valid_confirmed_instrument()
        incompatible_mapping = make_incompatible_instrument_version(inst)
        with pytest.raises(ValidationError) as exc:
            _with_updates(inst, dataset_mapping=incompatible_mapping)
        assert "no coincide con la versión actual del instrumento" in str(exc.value)

    def test_fixture_10_valid_reviewed_without_dataset(self):
        """Fixture 10: Instrumento válido revisado sin dataset asociado es aceptado."""
        inst = make_valid_reviewed_without_dataset()
        assert inst.status == "reviewed"
        assert inst.dataset_mapping is None
        assert inst.confirmation.state == "confirmed"
        assert len(inst.items) == 1

    def test_regression_1_confirmation_state_pending_and_confirmed(self):
        """Regresión 1: Confirmación humana con state='pending' o state='confirmed'."""
        pending = InstrumentConfirmation(state="pending")
        assert pending.state == "pending"
        assert pending.confirmed_at is None
        assert pending.confirmer_ref is None

        now = datetime.now(UTC)
        confirmed = InstrumentConfirmation(
            state="confirmed",
            confirmed_at=now,
            confirmer_ref="revisor_humano",
        )
        assert confirmed.state == "confirmed"
        assert confirmed.confirmed_at == now
        assert confirmed.confirmer_ref == "revisor_humano"

    def test_regression_2_rejection_of_confirmed_boolean_field(self):
        """Regresión 2: Rechazo de confirmed: bool en lugar de state."""
        with pytest.raises(ValidationError):
            InstrumentConfirmation.model_validate({"confirmed": True})

    def test_regression_3_public_identifiers_item_id_and_scoring_rule_id(self):
        """Regresión 3: Los identificadores públicos deben ser item_id y scoring_rule_id."""
        item_id = uuid4()
        rule_id = uuid4()
        dim_id = uuid4()
        item = InstrumentItem(
            item_id=item_id,
            variable_id=uuid4(),
            dimension_id=dim_id,
            indicator_id=uuid4(),
            text="Pregunta de prueba",
            response_type="single_choice",
            response_options=standard_likert_options(),
        )
        assert item.item_id == item_id
        assert hasattr(item, "item_id")
        assert not hasattr(item, "id")

        rule = ScoringRule(
            scoring_rule_id=rule_id,
            scope="dimension",
            dimension_id=dim_id,
            item_ids=[item_id],
            aggregation="sum",
            missing_policy="all_required",
            confirmed=True,
        )
        assert rule.scoring_rule_id == rule_id
        assert hasattr(rule, "scoring_rule_id")
        assert not hasattr(rule, "id")

    def test_regression_4_and_5_response_options_with_numeric_value_and_text_codes(self):
        """Regresión 4 y 5: Presencia de numeric_value y soporte para códigos textuales."""
        opt = ResponseOption(code="TA", label="Totalmente de Acuerdo", numeric_value=5.0)
        assert opt.code == "TA"
        assert opt.numeric_value == 5.0
        assert opt.label == "Totalmente de Acuerdo"

        # Opciones numéricas con código textual conservado
        options = [
            ResponseOption(code="bajo", label="Nivel Bajo", numeric_value=1.0),
            ResponseOption(code="medio", label="Nivel Medio", numeric_value=2.0),
            ResponseOption(code="alto", label="Nivel Alto", numeric_value=3.0),
        ]
        item = InstrumentItem(
            item_id=uuid4(),
            variable_id=uuid4(),
            dimension_id=uuid4(),
            indicator_id=uuid4(),
            text="Reactivo ordinal con códigos de texto",
            response_type="single_choice",
            response_options=options,
        )
        assert len(item.response_options) == 3
        assert item.response_options[0].code == "bajo"
        assert item.response_options[0].numeric_value == 1.0

    def test_regression_6_rejection_of_invalid_scope(self):
        """Regresión 6: Rechazo de scope fuera de 'dimension' o 'instrument'."""
        with pytest.raises(ValidationError):
            ScoringRule(
                scoring_rule_id=uuid4(),
                scope="variable",  # No permitido en contrato acordado
                dimension_id=uuid4(),
                item_ids=[uuid4()],
                aggregation="sum",
            )

    def test_regression_7_validation_of_item_ids_within_scoring_rules(self):
        """Regresión 7: Validación de que item_ids pertenezcan a la dimensión objetivo."""
        inst = make_valid_confirmed_instrument()
        other_dim_id = uuid4()
        other_dim = InstrumentDimension(
            dimension_id=other_dim_id,
            variable_id=inst.variables[0].variable_id,
            name="Segunda Dimensión",
        )
        # Regla apunta a other_dim pero incluye ítems de la primera dimensión
        bad_rule = ScoringRule(
            scoring_rule_id=uuid4(),
            scope="dimension",
            dimension_id=other_dim_id,
            item_ids=[inst.items[0].item_id],
            aggregation="sum",
            confirmed=True,
        )
        with pytest.raises(ValidationError) as exc:
            _with_updates(
                inst,
                dimensions=inst.dimensions + [other_dim],
                scoring_rules=[bad_rule],
            )
        assert "pertenece a otra dimensión" in str(exc.value)

    def test_regression_8_rejection_of_incompatible_provenance(self):
        """Regresión 8: Rechazo de source_kind no admitido (ej. 'methodology')."""
        with pytest.raises(ValidationError):
            InstrumentProvenance(
                source_kind="methodology",  # Incompatible
                methodology_review_id=uuid4(),
                methodology_review_version=1,
                methodology_review_hash="a" * 64,
            )

    def test_regression_9_dataset_mapping_confirmation_integrity(self):
        """Regresión 9: Integridad de dataset_mapping.confirmation."""
        item_id = uuid4()
        # Mapeo confirmed con confirmación pending es rechazado
        with pytest.raises(ValidationError) as exc:
            DatasetMapping(
                dataset_id=uuid4(),
                dataset_hash="a" * 64,
                instrument_version=0,
                item_columns=[ItemColumnMapping(item_id=item_id, column_name="col1")],
                status="confirmed",
                confirmation=InstrumentConfirmation(state="pending"),
            )
        assert "confirmation.state='confirmed'" in str(exc.value)

    def test_regression_10_serialization_and_deserialization_fidelity(self):
        """Regresión 10: Serialización y deserialización fidedigna sin pérdida de campos."""
        original = make_valid_confirmed_instrument()
        json_str = original.model_dump_json()
        restored = InstrumentContext.model_validate_json(json_str)

        assert restored.instrument_id == original.instrument_id
        assert restored.items[0].item_id == original.items[0].item_id
        assert restored.items[0].response_options[0].code == "1"
        assert restored.items[0].response_options[0].numeric_value == 1.0
        assert (
            restored.scoring_rules[0].scoring_rule_id == original.scoring_rules[0].scoring_rule_id
        )
        assert restored.confirmation.state == "confirmed"
        assert restored == original

    def test_regression_11_rejection_of_extra_forbidden_fields(self):
        """Regresión 11: Rechazo estricto de campos extra no autorizados (extra='forbid')."""
        with pytest.raises(ValidationError):
            ResponseOption(
                code="1",
                label="Uno",
                numeric_value=1.0,
                extra_field="prohibido",
            )
        with pytest.raises(ValidationError):
            InstrumentConfirmation(
                state="pending",
                unexpected="prohibido",
            )

    def test_regression_12_json_schema_compatibility(self):
        """Regresión 12: JSON Schema compatible con la estructura pública acordada."""
        schema = InstrumentContext.model_json_schema()
        assert schema["type"] == "object"
        assert "schema_version" in schema["properties"]
        assert "instrument_id" in schema["properties"]
        assert "scoring_rules" in schema["properties"]
        assert "dataset_mapping" in schema["properties"]
        assert "items" in schema["properties"]

    def test_reviewed_instrument_must_have_confirmed_state(self):
        """Un instrumento en status='reviewed' debe tener confirmation.state='confirmed'."""
        inst = make_valid_reviewed_without_dataset()
        with pytest.raises(ValidationError) as exc:
            _with_updates(
                inst,
                confirmation=InstrumentConfirmation(state="pending"),
            )
        assert "requiere confirmation.state='confirmed'" in str(exc.value)

    def test_reviewed_instrument_requires_provenance_methodology(self):
        """Un instrumento en status='reviewed' sin procedencia metodológica es rechazado."""
        inst = make_valid_reviewed_without_dataset()
        with pytest.raises(ValidationError) as exc:
            _with_updates(inst, provenance=None)
        assert "requiere declarar obligatoriamente 'provenance'" in str(exc.value)

    def test_draft_instrument_cannot_have_confirmed_state(self):
        """Un instrumento en status='draft' no puede tener confirmation.state='confirmed'."""
        inst = make_valid_confirmed_instrument()
        with pytest.raises(ValidationError) as exc:
            _with_updates(inst, status="draft")
        assert "no puede permanecer en estado 'draft'" in str(exc.value)

    def test_pii_column_detection_and_rejection(self):
        assert is_pii_column("dni_encuestado") is True
        assert is_pii_column("correo_electronico") is True
        assert is_pii_column("nombre_alumno") is True
        assert is_pii_column("p1_satisfaccion") is False

        with pytest.raises(ValidationError) as exc:
            ItemColumnMapping(item_id=uuid4(), column_name="dni_sujeto")
        assert "identificador personal o PII" in str(exc.value)

    def test_response_option_finite_numeric_value_validation(self):
        """Valida que numeric_value rechace NaN e infinitos."""
        with pytest.raises(ValidationError) as exc:
            ResponseOption(code="A", label="Opción", numeric_value=float("nan"))
        assert "número finito" in str(exc.value)

        with pytest.raises(ValidationError) as exc:
            ResponseOption(code="A", label="Opción", numeric_value=float("inf"))
        assert "número finito" in str(exc.value)

        with pytest.raises(ValidationError) as exc:
            ResponseOption(code="A", label="Opción", numeric_value=float("-inf"))
        assert "número finito" in str(exc.value)

    def test_item_bounds_finite_validation(self):
        """Valida que valid_min y valid_max rechacen NaN e infinitos."""
        opts = standard_likert_options()
        with pytest.raises(ValidationError) as exc:
            InstrumentItem(
                item_id=uuid4(),
                variable_id=uuid4(),
                dimension_id=uuid4(),
                indicator_id=uuid4(),
                text="Texto",
                response_type="single_choice",
                response_options=opts,
                valid_min=float("nan"),
                valid_max=5.0,
            )
        assert "números finitos" in str(exc.value)

        with pytest.raises(ValidationError) as exc:
            InstrumentItem(
                item_id=uuid4(),
                variable_id=uuid4(),
                dimension_id=uuid4(),
                indicator_id=uuid4(),
                text="Texto",
                response_type="single_choice",
                response_options=opts,
                valid_min=1.0,
                valid_max=float("inf"),
            )
        assert "números finitos" in str(exc.value)

    def test_shared_contracts_remain_untouched(self):
        """Verifica que los contratos canónicos compartidos permanezcan 100% intactos."""
        assert ResearchPackage.__name__ == "ResearchPackage"
        assert DatasetReference.__name__ == "DatasetReference"
        assert AnalysisPlan.__name__ == "AnalysisPlan"
        assert AnalysisResult.__name__ == "AnalysisResult"
        assert ResearchVariable.__name__ == "ResearchVariable"
        assert ResearchHypothesis.__name__ == "ResearchHypothesis"

    def test_shared_instrument_contracts_canonical_location(self):
        """Verifica que la definición canónica resida en app.shared.instrument_contracts."""
        from pydantic import BaseModel

        from app.shared.instrument_contracts import (
            InstrumentContext as SharedInstrumentContext,
        )
        from app.shared.ports import InstrumentContextReader as SharedReaderProtocol

        assert SharedInstrumentContext is InstrumentContext
        assert issubclass(SharedInstrumentContext, BaseModel)
        assert SharedReaderProtocol is not None

    def test_range_validation_numeric_value_respects_declared_bounds(self):
        """B3: Las opciones de respuesta deben estar dentro de límites declarados."""
        opts_valid = [
            ResponseOption(code="1", label="Uno", numeric_value=1.0),
            ResponseOption(code="2", label="Dos", numeric_value=5.0),
        ]
        item = InstrumentItem(
            item_id=uuid4(),
            variable_id=uuid4(),
            dimension_id=uuid4(),
            indicator_id=uuid4(),
            text="Texto",
            response_type="single_choice",
            response_options=opts_valid,
            valid_min=1.0,
            valid_max=5.0,
        )
        assert item.valid_min == 1.0

        # Valor numérico menor que valid_min
        opts_below = [
            ResponseOption(code="0", label="Cero", numeric_value=0.5),
            ResponseOption(code="2", label="Dos", numeric_value=5.0),
        ]
        with pytest.raises(ValidationError) as exc:
            InstrumentItem(
                item_id=uuid4(),
                variable_id=uuid4(),
                dimension_id=uuid4(),
                indicator_id=uuid4(),
                text="Texto",
                response_type="single_choice",
                response_options=opts_below,
                valid_min=1.0,
                valid_max=5.0,
            )
        assert "inferior al límite valid_min" in str(exc.value)

        # Valor numérico mayor que valid_max
        opts_above = [
            ResponseOption(code="1", label="Uno", numeric_value=1.0),
            ResponseOption(code="6", label="Seis", numeric_value=6.0),
        ]
        with pytest.raises(ValidationError) as exc:
            InstrumentItem(
                item_id=uuid4(),
                variable_id=uuid4(),
                dimension_id=uuid4(),
                indicator_id=uuid4(),
                text="Texto",
                response_type="single_choice",
                response_options=opts_above,
                valid_min=1.0,
                valid_max=5.0,
            )
        assert "supera el límite valid_max" in str(exc.value)

    def test_range_semi_bounded_remains_admitted_pending_ratification(self):
        """B3: Rangos semiacotados siguen admitidos hasta ratificación formal."""
        item_min = InstrumentItem(
            item_id=uuid4(),
            variable_id=uuid4(),
            dimension_id=uuid4(),
            indicator_id=uuid4(),
            text="Tiempo en minutos (no acotado superiormente)",
            response_type="numeric",
            valid_min=0.0,
            valid_max=None,
        )
        assert item_min.valid_min == 0.0 and item_min.valid_max is None

        item_max = InstrumentItem(
            item_id=uuid4(),
            variable_id=uuid4(),
            dimension_id=uuid4(),
            indicator_id=uuid4(),
            text="Puntaje acotado superiormente",
            response_type="numeric",
            valid_min=None,
            valid_max=100.0,
        )
        assert item_max.valid_min is None and item_max.valid_max == 100.0

    def test_public_contract_examples_coherence_and_json_schema(self):
        """Tarea 2 y 4: Verifica ejemplos publicados según JSON Schema y Pydantic."""
        import json
        from pathlib import Path

        from jsonschema import Draft202012Validator

        root = Path(__file__).resolve().parents[3]
        schema_path = root / "docs" / "contracts" / "instrument_context_v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)

        ex1_path = (
            root / "docs" / "contracts" / "examples" / "instrument_confirmed_with_mapping.json"
        )
        ex1_raw = ex1_path.read_text(encoding="utf-8")
        ex1_json = json.loads(ex1_raw)
        validator.validate(ex1_json)
        inst1 = InstrumentContext.model_validate_json(ex1_raw)
        assert inst1.version >= 1
        assert inst1.status == "reviewed"
        assert inst1.variables[0].methodology_variable_id is not None
        assert inst1.updated_at == inst1.confirmation.confirmed_at
        assert inst1.dataset_mapping is not None
        assert inst1.dataset_mapping.status == "confirmed"

        ex2_path = (
            root / "docs" / "contracts" / "examples" / "instrument_reviewed_without_mapping.json"
        )
        ex2_raw = ex2_path.read_text(encoding="utf-8")
        ex2_json = json.loads(ex2_raw)
        validator.validate(ex2_json)
        inst2 = InstrumentContext.model_validate_json(ex2_raw)
        assert inst2.version >= 1
        assert inst2.status == "reviewed"
        assert inst2.variables[0].methodology_variable_id is not None
        assert inst2.updated_at == inst2.confirmation.confirmed_at
        assert inst2.dataset_mapping is None
