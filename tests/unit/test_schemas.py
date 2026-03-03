# tests/unit/test_schemas.py
"""Tests para los schemas Pydantic del LLM parser."""

import json
from datetime import date, time

import pytest
from pydantic import ValidationError

from src.db.models import Prioridad, TipoServicio
from src.llm.schemas import (
    Intent,
    IntentDetection,
    ParsedClosure,
    ParsedEdit,
    ParsedEvent,
    parse_llm_response,
)


class TestIntent:
    """Tests para el enum Intent."""

    def test_all_intents_exist(self):
        """Tiene las 10 intenciones esperadas."""
        expected = {
            "crear_evento",
            "editar_evento",
            "ver_eventos",
            "eliminar_evento",
            "terminar_evento",
            "ver_contactos",
            "editar_contacto",
            "saludo",
            "ayuda",
            "desconocido",
        }
        assert {i.value for i in Intent} == expected

    def test_intent_count(self):
        """Son exactamente 10 intenciones."""
        assert len(Intent) == 10

    def test_intent_from_string(self):
        """Se puede crear desde string."""
        assert Intent("crear_evento") == Intent.CREAR_EVENTO


class TestParsedEvent:
    """Tests para el schema ParsedEvent."""

    def test_minimal_creation(self):
        """Se puede crear con defaults mínimos."""
        event = ParsedEvent()
        assert event.intent == Intent.CREAR_EVENTO
        assert event.tipo_servicio == TipoServicio.OTRO
        assert event.prioridad == Prioridad.NORMAL
        assert event.duracion_minutos == 60
        assert event.confidence == 1.0
        assert event.missing_fields == []
        assert event.clarification_question is None

    def test_full_creation(self):
        """Se puede crear con todos los campos."""
        event = ParsedEvent(
            cliente_nombre="Juan Pérez",
            cliente_telefono="+5491155551234",
            direccion="Av. Corrientes 1234",
            tipo_servicio=TipoServicio.INSTALACION,
            fecha=date(2026, 3, 15),
            hora=time(10, 0),
            duracion_minutos=90,
            notas="Llevar herramientas",
            prioridad=Prioridad.ALTA,
            confidence=0.95,
        )
        assert event.cliente_nombre == "Juan Pérez"
        assert event.tipo_servicio == TipoServicio.INSTALACION
        assert event.fecha == date(2026, 3, 15)
        assert event.hora == time(10, 0)
        assert event.duracion_minutos == 90
        assert event.prioridad == Prioridad.ALTA

    def test_tipo_servicio_never_null(self):
        """tipo_servicio=None se convierte a 'otro' (NUNCA null)."""
        event = ParsedEvent(tipo_servicio=None)
        assert event.tipo_servicio == TipoServicio.OTRO

    def test_hora_strips_tzinfo(self):
        """hora con tzinfo se convierte a naive para evitar errores de comparación."""
        event = ParsedEvent(hora="16:00:00+00:00")
        assert event.hora is not None
        assert event.hora.tzinfo is None
        assert event.hora == time(16, 0)

    def test_hora_naive_unchanged(self):
        """hora sin tzinfo se mantiene sin cambios."""
        event = ParsedEvent(hora="16:00")
        assert event.hora == time(16, 0)
        assert event.hora.tzinfo is None

    def test_tipo_servicio_from_string(self):
        """tipo_servicio acepta strings."""
        event = ParsedEvent(tipo_servicio="instalacion")
        assert event.tipo_servicio == TipoServicio.INSTALACION

    def test_confidence_default_is_one(self):
        """El default de confidence es 1.0 (no 0.0)."""
        event = ParsedEvent()
        assert event.confidence == 1.0

    def test_confidence_range_min(self):
        """confidence no puede ser menor a 0.0."""
        with pytest.raises(ValidationError):
            ParsedEvent(confidence=-0.1)

    def test_confidence_range_max(self):
        """confidence no puede ser mayor a 1.0."""
        with pytest.raises(ValidationError):
            ParsedEvent(confidence=1.1)

    def test_duracion_min_constraint(self):
        """duracion_minutos mínimo es 15."""
        with pytest.raises(ValidationError):
            ParsedEvent(duracion_minutos=10)

    def test_duracion_max_constraint(self):
        """duracion_minutos máximo es 480."""
        with pytest.raises(ValidationError):
            ParsedEvent(duracion_minutos=500)

    def test_needs_clarification_missing_fields(self):
        """needs_clarification es True si hay missing_fields."""
        event = ParsedEvent(missing_fields=["fecha"])
        assert event.needs_clarification is True

    def test_needs_clarification_low_confidence(self):
        """needs_clarification es True si confidence < 0.6."""
        event = ParsedEvent(confidence=0.5)
        assert event.needs_clarification is True

    def test_needs_clarification_false(self):
        """needs_clarification es False sin missing_fields y confidence alta."""
        event = ParsedEvent(confidence=0.9, missing_fields=[])
        assert event.needs_clarification is False

    def test_needs_clarification_ignores_optional_fields(self):
        """needs_clarification es False si solo faltan campos opcionales."""
        event = ParsedEvent(
            confidence=0.9,
            missing_fields=["telefono", "direccion", "notas"],
        )
        assert event.needs_clarification is False

    def test_needs_clarification_required_field_missing(self):
        """needs_clarification es True si falta un campo requerido."""
        for field in ("cliente_nombre", "fecha", "hora"):
            event = ParsedEvent(confidence=0.9, missing_fields=[field])
            assert event.needs_clarification is True, f"Debería ser True para {field}"

    def test_needs_clarification_mixed_fields(self):
        """needs_clarification es True si hay mezcla con al menos un requerido."""
        event = ParsedEvent(
            confidence=0.9,
            missing_fields=["telefono", "fecha"],
        )
        assert event.needs_clarification is True

    def test_is_complete_true(self):
        """is_complete es True con todos los datos obligatorios."""
        event = ParsedEvent(
            cliente_nombre="Juan",
            fecha=date(2026, 3, 15),
            hora=time(10, 0),
            confidence=0.9,
        )
        assert event.is_complete is True

    def test_is_complete_false_missing_name(self):
        """is_complete es False sin nombre."""
        event = ParsedEvent(
            fecha=date(2026, 3, 15),
            hora=time(10, 0),
            confidence=0.9,
        )
        assert event.is_complete is False

    def test_is_complete_false_missing_fecha(self):
        """is_complete es False sin fecha."""
        event = ParsedEvent(
            cliente_nombre="Juan",
            hora=time(10, 0),
            confidence=0.9,
        )
        assert event.is_complete is False

    def test_is_complete_false_missing_hora(self):
        """is_complete es False sin hora."""
        event = ParsedEvent(
            cliente_nombre="Juan",
            fecha=date(2026, 3, 15),
            confidence=0.9,
        )
        assert event.is_complete is False

    def test_is_complete_true_with_optional_missing_fields(self):
        """is_complete es True aunque missing_fields tenga campos opcionales."""
        event = ParsedEvent(
            cliente_nombre="Juan",
            fecha=date(2026, 3, 15),
            hora=time(10, 0),
            missing_fields=["direccion", "telefono"],
            confidence=0.9,
        )
        assert event.is_complete is True

    def test_is_complete_false_low_confidence(self):
        """is_complete es False si confidence < 0.6 aunque tenga los datos."""
        event = ParsedEvent(
            cliente_nombre="Juan",
            fecha=date(2026, 3, 15),
            hora=time(10, 0),
            confidence=0.5,
        )
        assert event.is_complete is False

    def test_has_date_but_no_time_true(self):
        """has_date_but_no_time es True con fecha pero sin hora."""
        event = ParsedEvent(fecha=date(2026, 3, 15))
        assert event.has_date_but_no_time is True

    def test_has_date_but_no_time_false_both(self):
        """has_date_but_no_time es False con fecha y hora."""
        event = ParsedEvent(fecha=date(2026, 3, 15), hora=time(10, 0))
        assert event.has_date_but_no_time is False

    def test_has_date_but_no_time_false_no_date(self):
        """has_date_but_no_time es False sin fecha."""
        event = ParsedEvent()
        assert event.has_date_but_no_time is False

    def test_is_high_priority_true(self):
        """is_high_priority es True con prioridad alta."""
        event = ParsedEvent(prioridad=Prioridad.ALTA)
        assert event.is_high_priority is True

    def test_is_high_priority_false(self):
        """is_high_priority es False con prioridad normal."""
        event = ParsedEvent(prioridad=Prioridad.NORMAL)
        assert event.is_high_priority is False

    def test_prioridad_from_string(self):
        """prioridad acepta strings."""
        event = ParsedEvent(prioridad="alta")
        assert event.prioridad == Prioridad.ALTA


class TestParsedEdit:
    """Tests para el schema ParsedEdit."""

    def test_minimal_creation(self):
        """Se puede crear con defaults."""
        edit = ParsedEdit()
        assert edit.intent == Intent.EDITAR_EVENTO
        assert edit.changes == {}
        assert edit.clarification_question is None

    def test_with_changes(self):
        """Se puede crear con cambios."""
        edit = ParsedEdit(changes={"hora": "14:00", "notas": "test"})
        assert edit.changes["hora"] == "14:00"
        assert edit.changes["notas"] == "test"

    def test_with_clarification(self):
        """Se puede crear con pregunta de clarificación."""
        edit = ParsedEdit(clarification_question="¿Qué campo querés cambiar?")
        assert edit.clarification_question == "¿Qué campo querés cambiar?"


class TestParsedClosure:
    """Tests para el schema ParsedClosure."""

    def test_minimal_creation(self):
        """Se puede crear con defaults."""
        closure = ParsedClosure()
        assert closure.intent == Intent.TERMINAR_EVENTO
        assert closure.trabajo_realizado is None
        assert closure.monto_cobrado is None
        assert closure.notas_cierre is None
        assert closure.missing_fields == []

    def test_full_creation(self):
        """Se puede crear con todos los campos."""
        closure = ParsedClosure(
            trabajo_realizado="Instalación de 4 cámaras",
            monto_cobrado=150000.0,
            notas_cierre="Cliente satisfecho",
        )
        assert closure.trabajo_realizado == "Instalación de 4 cámaras"
        assert closure.monto_cobrado == 150000.0
        assert closure.notas_cierre == "Cliente satisfecho"

    def test_monto_zero_is_valid(self):
        """monto_cobrado=0 es válido (ej: garantía)."""
        closure = ParsedClosure(monto_cobrado=0.0)
        assert closure.monto_cobrado == 0.0

    def test_monto_negative_invalid(self):
        """monto_cobrado negativo no es válido."""
        with pytest.raises(ValidationError):
            ParsedClosure(monto_cobrado=-100.0)

    def test_with_missing_fields(self):
        """Se puede crear con campos faltantes."""
        closure = ParsedClosure(
            missing_fields=["trabajo_realizado", "monto_cobrado"],
            clarification_question="¿Qué trabajo se realizó y cuánto se cobró?",
        )
        assert len(closure.missing_fields) == 2
        assert closure.clarification_question is not None


class TestIntentDetection:
    """Tests para el schema IntentDetection."""

    def test_creation(self):
        """Se puede crear con los campos requeridos."""
        detection = IntentDetection(
            intent=Intent.CREAR_EVENTO,
            confidence=0.95,
        )
        assert detection.intent == Intent.CREAR_EVENTO
        assert detection.confidence == 0.95
        assert detection.extracted_data == {}

    def test_with_extracted_data(self):
        """Se puede crear con datos extraídos."""
        detection = IntentDetection(
            intent=Intent.CREAR_EVENTO,
            confidence=0.9,
            extracted_data={
                "cliente_nombre": "Juan",
                "tipo_servicio": "instalacion",
            },
        )
        assert detection.extracted_data["cliente_nombre"] == "Juan"

    def test_confidence_range(self):
        """confidence debe estar entre 0.0 y 1.0."""
        with pytest.raises(ValidationError):
            IntentDetection(intent=Intent.SALUDO, confidence=1.5)

        with pytest.raises(ValidationError):
            IntentDetection(intent=Intent.SALUDO, confidence=-0.1)

    def test_intent_required(self):
        """intent es campo requerido."""
        with pytest.raises(ValidationError):
            IntentDetection(confidence=0.5)


class TestParseLlmResponse:
    """Tests para la función parse_llm_response."""

    def test_valid_parsed_event(self):
        """Parsea un JSON válido de ParsedEvent."""
        raw = json.dumps(
            {
                "intent": "crear_evento",
                "cliente_nombre": "García",
                "tipo_servicio": "revision",
                "fecha": "2026-03-15",
                "hora": "10:00",
                "confidence": 0.9,
                "missing_fields": [],
            }
        )
        result = parse_llm_response(raw, ParsedEvent)
        assert isinstance(result, ParsedEvent)
        assert result.cliente_nombre == "García"
        assert result.tipo_servicio == TipoServicio.REVISION
        assert result.fecha == date(2026, 3, 15)

    def test_valid_intent_detection(self):
        """Parsea un JSON válido de IntentDetection."""
        raw = json.dumps(
            {
                "intent": "ver_eventos",
                "confidence": 0.9,
                "extracted_data": {},
            }
        )
        result = parse_llm_response(raw, IntentDetection)
        assert isinstance(result, IntentDetection)
        assert result.intent == Intent.VER_EVENTOS

    def test_invalid_json_raises(self):
        """JSON inválido lanza ValueError."""
        with pytest.raises(ValueError, match="Respuesta del LLM inválida"):
            parse_llm_response("no es json {{{", ParsedEvent)

    def test_invalid_schema_raises(self):
        """JSON válido pero que no cumple el schema lanza ValueError."""
        raw = json.dumps({"intent": "intent_inexistente", "confidence": 0.5})
        with pytest.raises(ValueError, match="Respuesta del LLM inválida"):
            parse_llm_response(raw, IntentDetection)

    def test_tipo_servicio_null_becomes_otro(self):
        """tipo_servicio=null en JSON se convierte a 'otro'."""
        raw = json.dumps(
            {
                "intent": "crear_evento",
                "tipo_servicio": None,
                "confidence": 0.9,
                "missing_fields": [],
            }
        )
        result = parse_llm_response(raw, ParsedEvent)
        assert result.tipo_servicio == TipoServicio.OTRO

    def test_valid_parsed_edit(self):
        """Parsea un JSON válido de ParsedEdit."""
        raw = json.dumps(
            {
                "intent": "editar_evento",
                "changes": {"hora": "14:00"},
                "clarification_question": None,
            }
        )
        result = parse_llm_response(raw, ParsedEdit)
        assert isinstance(result, ParsedEdit)
        assert result.changes == {"hora": "14:00"}

    def test_valid_parsed_closure(self):
        """Parsea un JSON válido de ParsedClosure."""
        raw = json.dumps(
            {
                "intent": "terminar_evento",
                "trabajo_realizado": "Instalación completada",
                "monto_cobrado": 50000.0,
                "missing_fields": [],
            }
        )
        result = parse_llm_response(raw, ParsedClosure)
        assert isinstance(result, ParsedClosure)
        assert result.monto_cobrado == 50000.0
