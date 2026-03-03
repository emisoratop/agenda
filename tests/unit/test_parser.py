# tests/unit/test_parser.py
"""Tests para el parser LLM que interpreta mensajes de usuario."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import LLMParsingError, LLMUnavailableError
from src.db.models import Evento, TipoServicio
from src.llm.client import LLMChain, LLMResponse
from src.llm.parser import LLMParser, _MAX_PARSE_RETRIES
from src.llm.prompts import STATIC_FALLBACK
from src.llm.schemas import (
    Intent,
    IntentDetection,
    ParsedClosure,
    ParsedEdit,
    ParsedEvent,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_chain(response_content: str) -> LLMChain:
    """Crea un LLMChain mock que devuelve el contenido indicado."""
    chain = MagicMock(spec=LLMChain)
    chain.complete = AsyncMock(
        return_value=LLMResponse(
            content=response_content,
            model="test-model",
            provider="test-provider",
        )
    )
    return chain


def _make_failing_chain(error: Exception | None = None) -> LLMChain:
    """Crea un LLMChain mock que siempre lanza RuntimeError."""
    chain = MagicMock(spec=LLMChain)
    chain.complete = AsyncMock(
        side_effect=error or RuntimeError("Todos los LLM fallaron")
    )
    return chain


def _sample_evento() -> Evento:
    """Evento de ejemplo para tests de edición."""
    return Evento(
        id=1,
        cliente_id=1,
        tipo_servicio=TipoServicio.REVISION,
        fecha_hora=datetime(2026, 3, 15, 10, 0),
        duracion_minutos=60,
        notas="Revisar cámaras",
    )


# ── Tests: _extract_json ─────────────────────────────────────────────────────


class TestExtractJson:
    """Tests para la extracción de JSON de respuestas crudas del LLM."""

    def test_json_directo(self):
        """Extrae JSON cuando es el contenido directo."""
        raw = '{"intent": "saludo", "confidence": 0.9, "extracted_data": {}}'
        result = LLMParser._extract_json(raw)
        assert json.loads(result) == {
            "intent": "saludo",
            "confidence": 0.9,
            "extracted_data": {},
        }

    def test_json_en_bloque_markdown(self):
        """Extrae JSON envuelto en bloque ```json ... ```."""
        raw = '```json\n{"intent": "crear_evento", "confidence": 0.95}\n```'
        result = LLMParser._extract_json(raw)
        parsed = json.loads(result)
        assert parsed["intent"] == "crear_evento"

    def test_json_en_bloque_markdown_sin_tag(self):
        """Extrae JSON envuelto en bloque ``` ... ``` sin tag json."""
        raw = '```\n{"intent": "saludo"}\n```'
        result = LLMParser._extract_json(raw)
        assert json.loads(result)["intent"] == "saludo"

    def test_json_con_texto_antes_y_despues(self):
        """Extrae JSON cuando hay texto libre antes y después."""
        raw = 'Aquí va la respuesta:\n{"intent": "ver_eventos"}\nEso es todo.'
        result = LLMParser._extract_json(raw)
        assert json.loads(result)["intent"] == "ver_eventos"

    def test_texto_sin_json_devuelve_tal_cual(self):
        """Si no hay JSON reconocible, devuelve el texto tal cual (stripped)."""
        raw = "  Esto no es JSON  "
        result = LLMParser._extract_json(raw)
        assert result == "Esto no es JSON"

    def test_json_con_llaves_anidadas(self):
        """Extrae correctamente JSON con objetos anidados."""
        raw = '{"changes": {"hora": "14:00", "notas": "llevar repuestos"}}'
        result = LLMParser._extract_json(raw)
        parsed = json.loads(result)
        assert parsed["changes"]["hora"] == "14:00"

    def test_json_en_markdown_con_espacios(self):
        """Extrae JSON de bloque markdown con espacios extra."""
        raw = '```json  \n  {"intent": "ayuda"}  \n  ```'
        result = LLMParser._extract_json(raw)
        assert json.loads(result)["intent"] == "ayuda"

    def test_multiples_bloques_json_toma_primero(self):
        """Si hay múltiples bloques markdown, extrae el primero."""
        raw = '```json\n{"first": true}\n```\n```json\n{"second": true}\n```'
        result = LLMParser._extract_json(raw)
        assert json.loads(result) == {"first": True}


# ── Tests: detect_intent ──────────────────────────────────────────────────────


class TestDetectIntent:
    """Tests para la detección de intención."""

    async def test_detecta_saludo(self):
        """Detecta intención 'saludo' con alta confianza."""
        response_json = json.dumps(
            {"intent": "saludo", "confidence": 0.95, "extracted_data": {}}
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        result = await parser.detect_intent("Hola, buenas tardes")

        assert isinstance(result, IntentDetection)
        assert result.intent == Intent.SALUDO
        assert result.confidence == 0.95
        assert result.extracted_data == {}

    async def test_detecta_crear_evento_con_datos(self):
        """Detecta intención 'crear_evento' y extrae datos asociados."""
        response_json = json.dumps(
            {
                "intent": "crear_evento",
                "confidence": 0.9,
                "extracted_data": {
                    "cliente_nombre": "García",
                    "tipo_servicio": "instalacion",
                },
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        result = await parser.detect_intent("Agendar instalación para García mañana")

        assert result.intent == Intent.CREAR_EVENTO
        assert result.extracted_data["cliente_nombre"] == "García"

    async def test_detecta_ver_eventos(self):
        """Detecta intención 'ver_eventos'."""
        response_json = json.dumps(
            {"intent": "ver_eventos", "confidence": 0.9, "extracted_data": {}}
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        result = await parser.detect_intent("¿Qué tengo agendado?")

        assert result.intent == Intent.VER_EVENTOS

    async def test_detecta_eliminar_evento(self):
        """Detecta intención 'eliminar_evento'."""
        response_json = json.dumps(
            {
                "intent": "eliminar_evento",
                "confidence": 0.9,
                "extracted_data": {"cliente_nombre": "López"},
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        result = await parser.detect_intent("Cancelá el evento de López")

        assert result.intent == Intent.ELIMINAR_EVENTO
        assert result.extracted_data["cliente_nombre"] == "López"

    async def test_detecta_terminar_evento(self):
        """Detecta intención 'terminar_evento' con monto extraído."""
        response_json = json.dumps(
            {
                "intent": "terminar_evento",
                "confidence": 0.85,
                "extracted_data": {
                    "cliente_nombre": "Martínez",
                    "monto_cobrado": 80000,
                },
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        result = await parser.detect_intent("Ya terminé con Martínez, cobré $80.000")

        assert result.intent == Intent.TERMINAR_EVENTO
        assert result.extracted_data["monto_cobrado"] == 80000

    async def test_detecta_ayuda(self):
        """Detecta intención 'ayuda'."""
        response_json = json.dumps(
            {"intent": "ayuda", "confidence": 0.85, "extracted_data": {}}
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        result = await parser.detect_intent("¿Qué podés hacer?")

        assert result.intent == Intent.AYUDA

    async def test_detecta_desconocido(self):
        """Detecta intención 'desconocido' para texto ambiguo."""
        response_json = json.dumps(
            {"intent": "desconocido", "confidence": 0.3, "extracted_data": {}}
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        result = await parser.detect_intent("asdjfklasdjf")

        assert result.intent == Intent.DESCONOCIDO
        assert result.confidence == 0.3

    async def test_llama_chain_con_mensajes_correctos(self):
        """Verifica que se pasa system prompt + user prompt a la cadena."""
        response_json = json.dumps(
            {"intent": "saludo", "confidence": 0.9, "extracted_data": {}}
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        await parser.detect_intent("Hola")

        chain.complete.assert_called_once()
        call_kwargs = chain.complete.call_args
        messages = call_kwargs.kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "Hola" in messages[1]["content"]


# ── Tests: parse_create_event ─────────────────────────────────────────────────


class TestParseCreateEvent:
    """Tests para el parsing de creación de evento."""

    async def test_evento_completo(self):
        """Parsea un evento con todos los datos disponibles."""
        response_json = json.dumps(
            {
                "intent": "crear_evento",
                "cliente_nombre": "Juan Pérez",
                "cliente_telefono": "351-123456",
                "direccion": "Balcarce 132",
                "tipo_servicio": "instalacion",
                "fecha": "2026-03-15",
                "hora": "10:00",
                "duracion_minutos": 90,
                "notas": "Instalar 4 cámaras",
                "prioridad": "normal",
                "missing_fields": [],
                "clarification_question": None,
                "confidence": 0.95,
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        result = await parser.parse_create_event(
            "Mañana a las 10 instalación de cámaras para Juan Pérez en Balcarce 132"
        )

        assert isinstance(result, ParsedEvent)
        assert result.cliente_nombre == "Juan Pérez"
        assert result.cliente_telefono == "351-123456"
        assert result.direccion == "Balcarce 132"
        assert result.tipo_servicio == TipoServicio.INSTALACION
        assert str(result.fecha) == "2026-03-15"
        assert str(result.hora) == "10:00:00"
        assert result.duracion_minutos == 90
        assert result.confidence == 0.95
        assert result.is_complete is True
        assert result.missing_fields == []

    async def test_evento_sin_fecha_ni_hora(self):
        """Evento sin fecha y hora: pide solo la fecha."""
        response_json = json.dumps(
            {
                "intent": "crear_evento",
                "cliente_nombre": "García",
                "tipo_servicio": "revision",
                "fecha": None,
                "hora": None,
                "missing_fields": ["fecha"],
                "clarification_question": "¿Para qué fecha es la revisión de García?",
                "confidence": 0.7,
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        result = await parser.parse_create_event("Agendar revisión para García")

        assert result.fecha is None
        assert result.hora is None
        assert "fecha" in result.missing_fields
        assert result.clarification_question is not None
        assert result.needs_clarification is True
        assert result.is_complete is False

    async def test_evento_con_fecha_sin_hora(self):
        """Evento con fecha pero sin hora: has_date_but_no_time = True."""
        response_json = json.dumps(
            {
                "intent": "crear_evento",
                "cliente_nombre": "López",
                "tipo_servicio": "instalacion",
                "fecha": "2026-03-20",
                "hora": None,
                "missing_fields": ["hora"],
                "clarification_question": None,
                "confidence": 0.85,
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        result = await parser.parse_create_event("Instalación para López el viernes")

        assert result.has_date_but_no_time is True
        assert result.clarification_question is None  # Sistema muestra botones

    async def test_evento_prioridad_alta(self):
        """Evento con prioridad alta detectada por 'urgente'."""
        response_json = json.dumps(
            {
                "intent": "crear_evento",
                "cliente_nombre": "Martínez",
                "tipo_servicio": "reparacion",
                "fecha": "2026-03-10",
                "hora": "09:00",
                "prioridad": "alta",
                "missing_fields": [],
                "clarification_question": None,
                "confidence": 0.9,
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        result = await parser.parse_create_event(
            "Reparación urgente de alarma para Martínez mañana a las 9"
        )

        assert result.is_high_priority is True

    async def test_tipo_servicio_null_se_convierte_a_otro(self):
        """Si el LLM devuelve tipo_servicio=null, el validador lo pone en 'otro'."""
        response_json = json.dumps(
            {
                "intent": "crear_evento",
                "cliente_nombre": "Test",
                "tipo_servicio": None,
                "fecha": "2026-03-15",
                "hora": "10:00",
                "missing_fields": [],
                "confidence": 0.8,
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        result = await parser.parse_create_event("Algo para Test mañana a las 10")

        assert result.tipo_servicio == TipoServicio.OTRO

    async def test_respuesta_en_bloque_markdown(self):
        """Parsea correctamente JSON envuelto en bloque ```json```."""
        inner_json = json.dumps(
            {
                "intent": "crear_evento",
                "cliente_nombre": "Rodríguez",
                "tipo_servicio": "mantenimiento",
                "fecha": "2026-03-18",
                "hora": "14:00",
                "missing_fields": [],
                "confidence": 0.9,
            }
        )
        markdown_response = f"```json\n{inner_json}\n```"
        chain = _make_chain(markdown_response)
        parser = LLMParser(chain)

        result = await parser.parse_create_event(
            "Mantenimiento para Rodríguez el miércoles a las 14"
        )

        assert isinstance(result, ParsedEvent)
        assert result.cliente_nombre == "Rodríguez"
        assert result.tipo_servicio == TipoServicio.MANTENIMIENTO


# ── Tests: parse_edit_event ───────────────────────────────────────────────────


class TestParseEditEvent:
    """Tests para el parsing de edición de evento."""

    async def test_editar_hora(self):
        """Parsea cambio de hora de un evento existente."""
        response_json = json.dumps(
            {
                "intent": "editar_evento",
                "changes": {"hora": "14:00"},
                "clarification_question": None,
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)
        evento = _sample_evento()

        result = await parser.parse_edit_event("Pasalo a las 14", evento)

        assert isinstance(result, ParsedEdit)
        assert result.changes == {"hora": "14:00"}
        assert result.clarification_question is None

    async def test_editar_multiples_campos(self):
        """Parsea cambios en múltiples campos."""
        response_json = json.dumps(
            {
                "intent": "editar_evento",
                "changes": {
                    "fecha": "2026-03-09",
                    "duracion_minutos": "120",
                },
                "clarification_question": None,
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)
        evento = _sample_evento()

        result = await parser.parse_edit_event(
            "Cambialo al lunes y que dure 2 horas", evento
        )

        assert "fecha" in result.changes
        assert "duracion_minutos" in result.changes

    async def test_editar_con_clarificacion(self):
        """Si no se entiende qué cambiar, pide clarificación."""
        response_json = json.dumps(
            {
                "intent": "editar_evento",
                "changes": {},
                "clarification_question": "¿Qué campo querés modificar?",
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)
        evento = _sample_evento()

        result = await parser.parse_edit_event("Cambialo", evento)

        assert result.changes == {}
        assert result.clarification_question is not None

    async def test_pasa_evento_actual_al_prompt(self):
        """Verifica que el evento actual se incluye en el prompt enviado al LLM."""
        response_json = json.dumps(
            {
                "intent": "editar_evento",
                "changes": {"hora": "15:00"},
                "clarification_question": None,
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)
        evento = _sample_evento()

        await parser.parse_edit_event("Pasalo a las 15", evento)

        chain.complete.assert_called_once()
        messages = chain.complete.call_args.kwargs["messages"]
        user_prompt = messages[1]["content"]
        # El prompt debe contener los delimitadores del evento
        assert "---BEGIN EVENT DATA---" in user_prompt
        assert "---END EVENT DATA---" in user_prompt
        # Y datos del evento serializado
        assert "revision" in user_prompt


# ── Tests: parse_closure ──────────────────────────────────────────────────────


class TestParseClosure:
    """Tests para el parsing de cierre de servicio."""

    async def test_cierre_completo(self):
        """Parsea cierre con todos los datos."""
        response_json = json.dumps(
            {
                "intent": "terminar_evento",
                "trabajo_realizado": "Instalación de 4 cámaras y DVR",
                "monto_cobrado": 150000.0,
                "notas_cierre": None,
                "missing_fields": [],
                "clarification_question": None,
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        result = await parser.parse_closure(
            "Se instalaron 4 cámaras y el DVR. Se cobró $150.000"
        )

        assert isinstance(result, ParsedClosure)
        assert result.trabajo_realizado == "Instalación de 4 cámaras y DVR"
        assert result.monto_cobrado == 150000.0
        assert result.missing_fields == []

    async def test_cierre_sin_datos_pide_clarificacion(self):
        """Si el usuario solo dice 'Listo', pide más datos."""
        response_json = json.dumps(
            {
                "intent": "terminar_evento",
                "trabajo_realizado": None,
                "monto_cobrado": None,
                "notas_cierre": None,
                "missing_fields": ["trabajo_realizado", "monto_cobrado"],
                "clarification_question": "¿Qué trabajo se realizó y cuánto se cobró?",
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        result = await parser.parse_closure("Listo")

        assert result.trabajo_realizado is None
        assert result.monto_cobrado is None
        assert "trabajo_realizado" in result.missing_fields
        assert result.clarification_question is not None

    async def test_cierre_con_monto_cero(self):
        """Cierre con monto cero (garantía)."""
        response_json = json.dumps(
            {
                "intent": "terminar_evento",
                "trabajo_realizado": "Revisión completada",
                "monto_cobrado": 0.0,
                "notas_cierre": "Cubierto por garantía",
                "missing_fields": [],
                "clarification_question": None,
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        result = await parser.parse_closure(
            "Revisión hecha, no se cobró porque está en garantía"
        )

        assert result.monto_cobrado == 0.0
        assert result.notas_cierre == "Cubierto por garantía"


# ── Tests: Manejo de errores ──────────────────────────────────────────────────


class TestErrorHandling:
    """Tests para errores del parser: LLM caído y respuestas no parseables."""

    async def test_chain_falla_lanza_llm_unavailable(self):
        """Si la cadena LLM lanza RuntimeError, se convierte en LLMUnavailableError."""
        chain = _make_failing_chain()
        parser = LLMParser(chain)

        with pytest.raises(LLMUnavailableError) as exc_info:
            await parser.detect_intent("Hola")

        # El mensaje debe ser el fallback estático
        assert exc_info.value.message == STATIC_FALLBACK

    async def test_chain_falla_detalles_del_error(self):
        """LLMUnavailableError contiene los detalles del error original."""
        chain = _make_failing_chain(RuntimeError("Timeout en groq"))
        parser = LLMParser(chain)

        with pytest.raises(LLMUnavailableError) as exc_info:
            await parser.parse_create_event("Test")

        assert "Timeout en groq" in exc_info.value.details

    async def test_json_invalido_tras_reintentos_lanza_llm_parsing_error(self):
        """Si la respuesta no es JSON válido tras todos los reintentos, lanza LLMParsingError."""
        chain = _make_chain("Esto no es JSON para nada")
        parser = LLMParser(chain)

        with pytest.raises(LLMParsingError) as exc_info:
            await parser.detect_intent("Test")

        assert "No se pudo parsear" in exc_info.value.message
        # Debe haber llamado al chain _MAX_PARSE_RETRIES veces
        assert chain.complete.call_count == _MAX_PARSE_RETRIES

    async def test_schema_invalido_tras_reintentos_lanza_llm_parsing_error(self):
        """Si el JSON es válido pero no cumple el schema, lanza LLMParsingError tras reintentos."""
        # JSON válido pero sin campo obligatorio 'intent' para IntentDetection
        chain = _make_chain('{"bad_field": "value"}')
        parser = LLMParser(chain)

        with pytest.raises(LLMParsingError):
            await parser.detect_intent("Test")

        assert chain.complete.call_count == _MAX_PARSE_RETRIES

    async def test_reintento_exitoso_tras_primer_json_invalido(self):
        """Si el primer intento devuelve JSON inválido pero el segundo es válido, tiene éxito."""
        valid_json = json.dumps(
            {"intent": "saludo", "confidence": 0.9, "extracted_data": {}}
        )
        chain = MagicMock(spec=LLMChain)
        chain.complete = AsyncMock(
            side_effect=[
                # Primer intento: respuesta inválida
                LLMResponse(content="not json", model="m", provider="p"),
                # Segundo intento: respuesta válida
                LLMResponse(content=valid_json, model="m", provider="p"),
            ]
        )
        parser = LLMParser(chain)

        result = await parser.detect_intent("Hola")

        assert isinstance(result, IntentDetection)
        assert result.intent == Intent.SALUDO
        assert chain.complete.call_count == 2

    async def test_max_parse_retries_es_2(self):
        """Verifica que _MAX_PARSE_RETRIES es 2 (como define la spec)."""
        assert _MAX_PARSE_RETRIES == 2

    async def test_chain_falla_en_parse_edit_lanza_unavailable(self):
        """LLMUnavailableError también se lanza desde parse_edit_event."""
        chain = _make_failing_chain()
        parser = LLMParser(chain)
        evento = _sample_evento()

        with pytest.raises(LLMUnavailableError):
            await parser.parse_edit_event("Cambiar hora", evento)

    async def test_chain_falla_en_parse_closure_lanza_unavailable(self):
        """LLMUnavailableError también se lanza desde parse_closure."""
        chain = _make_failing_chain()
        parser = LLMParser(chain)

        with pytest.raises(LLMUnavailableError):
            await parser.parse_closure("Listo")


# ── Tests: Integración prompts + parser ───────────────────────────────────────


class TestPromptIntegration:
    """Tests que verifican que los prompts correctos se pasan al LLM."""

    async def test_create_event_prompt_contiene_mensaje_usuario(self):
        """El prompt de creación incluye el texto del usuario."""
        response_json = json.dumps(
            {
                "intent": "crear_evento",
                "cliente_nombre": "Test",
                "tipo_servicio": "otro",
                "missing_fields": ["fecha"],
                "confidence": 0.5,
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        await parser.parse_create_event("Instalar cámaras para Pedro mañana")

        messages = chain.complete.call_args.kwargs["messages"]
        user_content = messages[1]["content"]
        assert "Instalar cámaras para Pedro mañana" in user_content

    async def test_closure_prompt_contiene_mensaje_usuario(self):
        """El prompt de cierre incluye el texto del usuario."""
        response_json = json.dumps(
            {
                "intent": "terminar_evento",
                "trabajo_realizado": "Test",
                "missing_fields": [],
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        await parser.parse_closure("Se instalaron 4 cámaras")

        messages = chain.complete.call_args.kwargs["messages"]
        user_content = messages[1]["content"]
        assert "Se instalaron 4 cámaras" in user_content

    async def test_system_prompt_contiene_fecha_actual(self):
        """El system prompt incluye la fecha y día actuales."""
        response_json = json.dumps(
            {"intent": "saludo", "confidence": 0.9, "extracted_data": {}}
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)

        await parser.detect_intent("Hola")

        messages = chain.complete.call_args.kwargs["messages"]
        system_content = messages[0]["content"]
        # Debe contener una fecha en formato YYYY-MM-DD
        assert "2026" in system_content  # Año actual del entorno
        # Debe contener el nombre del día en español
        days_es = [
            "lunes",
            "martes",
            "miércoles",
            "jueves",
            "viernes",
            "sábado",
            "domingo",
        ]
        assert any(day in system_content for day in days_es)

    async def test_edit_event_sanitiza_comillas_en_mensaje(self):
        """El prompt de edición escapa comillas dobles del mensaje del usuario."""
        response_json = json.dumps(
            {
                "intent": "editar_evento",
                "changes": {"notas": "test"},
                "clarification_question": None,
            }
        )
        chain = _make_chain(response_json)
        parser = LLMParser(chain)
        evento = _sample_evento()

        await parser.parse_edit_event('Agregá nota: "urgente"', evento)

        messages = chain.complete.call_args.kwargs["messages"]
        user_content = messages[1]["content"]
        # Las comillas dobles deben estar escapadas
        assert '\\"urgente\\"' in user_content
