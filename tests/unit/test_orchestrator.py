# tests/unit/test_orchestrator.py
"""Tests unitarios para el Orchestrator — todas las dependencias mockeadas."""

from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from src.core.result import AvailableSlot, ResultStatus
from src.db.models import (
    Cliente,
    EstadoEvento,
    Evento,
    Prioridad,
    TipoServicio,
)
from src.llm.schemas import (
    Intent,
    IntentDetection,
    ParsedClosure,
    ParsedEdit,
    ParsedEvent,
)
from src.orchestrator.orchestrator import (
    Orchestrator,
    _validate_event_date,
    _validate_event_datetime,
    _validate_work_hours,
)

TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_settings():
    """Settings mockeado con horarios laborales por defecto."""
    settings = MagicMock()
    settings.work_days_weekday_start = "15:00"
    settings.work_days_weekday_end = "21:00"
    settings.work_days_saturday_start = "08:00"
    settings.work_days_saturday_end = "20:00"
    return settings


@pytest.fixture
def mock_repo():
    """Repository completamente mockeado."""
    repo = AsyncMock()
    repo.create_evento = AsyncMock(return_value=1)
    repo.create_cliente = AsyncMock(return_value=1)
    repo.get_evento_by_id = AsyncMock(return_value=None)
    repo.get_cliente_by_id = AsyncMock(return_value=None)
    repo.get_cliente_by_telefono = AsyncMock(return_value=None)
    repo.search_clientes_fuzzy = AsyncMock(return_value=[])
    repo.list_eventos_by_date = AsyncMock(return_value=[])
    repo.list_eventos_pendientes = AsyncMock(return_value=[])
    repo.list_eventos_hoy = AsyncMock(return_value=[])
    repo.list_clientes = AsyncMock(return_value=[])
    repo.update_evento = AsyncMock(return_value=True)
    repo.delete_evento = AsyncMock(return_value=True)
    repo.complete_evento = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_calendar():
    """Calendar client mockeado."""
    cal = AsyncMock()
    cal.create_event = AsyncMock(return_value="google_evt_123")
    cal.update_event = AsyncMock(return_value=True)
    cal.delete_event = AsyncMock(return_value=True)
    cal.complete_event = AsyncMock(return_value=True)
    return cal


@pytest.fixture
def mock_parser():
    """LLM Parser mockeado."""
    parser = AsyncMock()
    return parser


@pytest.fixture
def orchestrator(mock_repo, mock_calendar, mock_parser, mock_settings):
    """Orchestrator con todas las dependencias mockeadas."""
    return Orchestrator(
        repository=mock_repo,
        calendar_client=mock_calendar,
        llm_parser=mock_parser,
        settings=mock_settings,
    )


@pytest.fixture
def sample_cliente():
    """Cliente de ejemplo para tests."""
    return Cliente(
        id=1,
        nombre="Juan Pérez",
        telefono="+5491155551234",
        direccion="Av. Corrientes 1234",
    )


@pytest.fixture
def sample_evento():
    """Evento de ejemplo con google_event_id."""
    return Evento(
        id=1,
        cliente_id=1,
        google_event_id="google_evt_123",
        tipo_servicio=TipoServicio.INSTALACION,
        prioridad=Prioridad.NORMAL,
        fecha_hora=datetime(2026, 3, 15, 16, 0, tzinfo=TIMEZONE),
        duracion_minutos=60,
        notas="Instalar aire",
    )


# ── Validaciones de módulo ────────────────────────────────────────────────────


class TestValidateEventDate:
    """Tests para _validate_event_date()."""

    def test_fecha_futura_valida(self):
        """Una fecha mañana es válida."""
        tomorrow = datetime.now(TIMEZONE).date() + timedelta(days=1)
        ok, msg = _validate_event_date(tomorrow)
        assert ok is True
        assert msg == ""

    def test_fecha_pasada_invalida(self):
        """Una fecha de ayer es inválida."""
        yesterday = datetime.now(TIMEZONE).date() - timedelta(days=1)
        ok, msg = _validate_event_date(yesterday)
        assert ok is False
        assert "ya pasó" in msg

    def test_fecha_hoy_valida(self):
        """La fecha de hoy es válida."""
        today = datetime.now(TIMEZONE).date()
        ok, msg = _validate_event_date(today)
        assert ok is True

    def test_fecha_demasiado_lejana(self):
        """Más de 90 días es inválida."""
        far = datetime.now(TIMEZONE).date() + timedelta(days=91)
        ok, msg = _validate_event_date(far)
        assert ok is False
        assert "90 días" in msg


class TestValidateEventDatetime:
    """Tests para _validate_event_datetime()."""

    def test_datetime_futuro_valido(self):
        """Un datetime futuro es válido."""
        tomorrow = datetime.now(TIMEZONE).date() + timedelta(days=1)
        ok, msg = _validate_event_datetime(tomorrow, time(16, 0))
        assert ok is True
        assert msg == ""

    def test_datetime_pasado_invalido(self):
        """Un datetime ya pasado es inválido."""
        yesterday = datetime.now(TIMEZONE).date() - timedelta(days=1)
        ok, msg = _validate_event_datetime(yesterday, time(10, 0))
        assert ok is False
        assert "ya pasaron" in msg


class TestValidateWorkHours:
    """Tests para _validate_work_hours()."""

    def test_hora_dentro_del_horario(self, mock_settings):
        """16:00 lunes con 60min está dentro del horario (15:00-21:00)."""
        ok, msg = _validate_work_hours(time(16, 0), 60, 0, mock_settings)
        assert ok is True

    def test_hora_antes_del_horario(self, mock_settings):
        """10:00 lunes está antes del horario laboral."""
        ok, msg = _validate_work_hours(time(10, 0), 60, 0, mock_settings)
        assert ok is False
        assert "15:00" in msg

    def test_evento_excede_fin_jornada(self, mock_settings):
        """20:30 lunes con 60min termina a las 21:30, fuera de horario."""
        ok, msg = _validate_work_hours(time(20, 30), 60, 0, mock_settings)
        assert ok is False
        assert "21:00" in msg

    def test_domingo_no_se_trabaja(self, mock_settings):
        """Los domingos no se trabaja."""
        ok, msg = _validate_work_hours(time(10, 0), 60, 6, mock_settings)
        assert ok is False
        assert "domingos" in msg.lower()

    def test_sabado_horario_distinto(self, mock_settings):
        """Sábado 09:00 con 60min está dentro del horario (08:00-20:00)."""
        ok, msg = _validate_work_hours(time(9, 0), 60, 5, mock_settings)
        assert ok is True


# ── Creación de evento ────────────────────────────────────────────────────────


class TestCreateEventFromText:
    """Tests para create_event_from_text()."""

    async def test_sin_fecha_pide_fecha(self, orchestrator, mock_parser):
        """Si el parse no tiene fecha, pide la fecha."""
        mock_parser.parse_create_event.return_value = ParsedEvent(
            cliente_nombre="Juan",
            fecha=None,
            hora=None,
        )
        result = await orchestrator.create_event_from_text("turno para Juan", 123)
        assert result.status == ResultStatus.NEEDS_INPUT
        assert "fecha" in result.question.lower()

    async def test_con_fecha_sin_hora_devuelve_slots(
        self, orchestrator, mock_parser, mock_settings
    ):
        """Si tiene fecha pero no hora, devuelve slots disponibles."""
        # Usar fecha futura para que pase la validación
        future_date = datetime.now(TIMEZONE).date() + timedelta(days=1)
        # Asegurarse de que no sea domingo
        while future_date.weekday() == 6:
            future_date += timedelta(days=1)

        mock_parser.parse_create_event.return_value = ParsedEvent(
            cliente_nombre="Juan",
            fecha=future_date,
            hora=None,
        )
        # No hay eventos ese día → todos los slots libres
        orchestrator.repo.list_eventos_by_date.return_value = []

        result = await orchestrator.create_event_from_text(
            "turno para Juan el lunes", 123
        )
        assert result.status == ResultStatus.NEEDS_INPUT
        assert "available_slots" in result.data

    async def test_evento_completo_normal(self, orchestrator, mock_parser):
        """Evento completo con todos los datos → success con evento preparado."""
        future_date = datetime.now(TIMEZONE).date() + timedelta(days=1)
        while future_date.weekday() >= 5:
            future_date += timedelta(days=1)

        mock_parser.parse_create_event.return_value = ParsedEvent(
            cliente_nombre="Juan Pérez",
            cliente_telefono="+5491155551234",
            fecha=future_date,
            hora=time(16, 0),
            tipo_servicio=TipoServicio.INSTALACION,
            duracion_minutos=60,
        )
        # Sin conflictos
        orchestrator.repo.list_eventos_by_date.return_value = []
        # Resolver cliente: no existe → crear nuevo
        orchestrator.repo.get_cliente_by_telefono.return_value = None
        orchestrator.repo.search_clientes_fuzzy.return_value = []
        orchestrator.repo.create_cliente.return_value = 1

        result = await orchestrator.create_event_from_text("turno Juan 16hs", 123)
        assert result.ok
        assert "evento" in result.data
        assert "cliente" in result.data

    async def test_evento_alta_prioridad_bypass_conflicto(
        self, orchestrator, mock_parser
    ):
        """Prioridad alta omite la verificación de disponibilidad."""
        future_date = datetime.now(TIMEZONE).date() + timedelta(days=1)
        while future_date.weekday() >= 5:
            future_date += timedelta(days=1)

        mock_parser.parse_create_event.return_value = ParsedEvent(
            cliente_nombre="Juan",
            fecha=future_date,
            hora=time(16, 0),
            prioridad=Prioridad.ALTA,
        )
        # Hay un evento a las 16 pero prioridad alta lo ignora
        existing = Evento(
            id=99,
            cliente_id=2,
            tipo_servicio=TipoServicio.OTRO,
            fecha_hora=datetime.combine(future_date, time(16, 0), tzinfo=TIMEZONE),
            duracion_minutos=60,
        )
        orchestrator.repo.list_eventos_by_date.return_value = [existing]
        orchestrator.repo.get_cliente_by_telefono.return_value = None
        orchestrator.repo.search_clientes_fuzzy.return_value = []
        orchestrator.repo.create_cliente.return_value = 1

        result = await orchestrator.create_event_from_text("urgente Juan 16hs", 123)
        assert result.ok
        # _check_availability NO se llamó
        # El evento se creó exitosamente a pesar del conflicto

    async def test_conflicto_con_slots_disponibles(self, orchestrator, mock_parser):
        """Si hay conflicto, devuelve CONFLICT con slots alternativos."""
        future_date = datetime.now(TIMEZONE).date() + timedelta(days=1)
        while future_date.weekday() >= 5:
            future_date += timedelta(days=1)

        mock_parser.parse_create_event.return_value = ParsedEvent(
            cliente_nombre="Juan",
            fecha=future_date,
            hora=time(16, 0),
        )
        # Evento existente a las 16:00
        existing = Evento(
            id=99,
            cliente_id=2,
            tipo_servicio=TipoServicio.OTRO,
            fecha_hora=datetime.combine(future_date, time(16, 0), tzinfo=TIMEZONE),
            duracion_minutos=60,
        )
        orchestrator.repo.list_eventos_by_date.return_value = [existing]
        orchestrator.repo.get_cliente_by_telefono.return_value = None
        orchestrator.repo.search_clientes_fuzzy.return_value = []

        result = await orchestrator.create_event_from_text("turno Juan 16hs", 123)
        assert result.status == ResultStatus.CONFLICT
        assert "available_slots" in result.data

    async def test_error_generico_devuelve_error(self, orchestrator, mock_parser):
        """Si el parser explota, devuelve Result.error."""
        mock_parser.parse_create_event.side_effect = RuntimeError("LLM down")
        result = await orchestrator.create_event_from_text("algo", 123)
        assert result.status == ResultStatus.ERROR


# ── Save confirmed event ──────────────────────────────────────────────────────


class TestSaveConfirmedEvent:
    """Tests para save_confirmed_event()."""

    async def test_save_ok_bd_y_calendar(
        self, orchestrator, sample_evento, sample_cliente
    ):
        """Guarda en BD, crea en Calendar, vincula google_event_id."""
        sample_evento.id = None
        sample_evento.google_event_id = None
        orchestrator.repo.create_evento.return_value = 1
        orchestrator.calendar.create_event.return_value = "google_evt_new"

        result = await orchestrator.save_confirmed_event(sample_evento, sample_cliente)
        assert result.ok
        orchestrator.repo.create_evento.assert_awaited_once()
        orchestrator.calendar.create_event.assert_awaited_once()
        orchestrator.repo.update_evento.assert_awaited_once()

    async def test_rollback_si_calendar_falla(
        self, orchestrator, sample_evento, sample_cliente
    ):
        """Si Calendar falla, se hace rollback eliminando de la BD."""
        sample_evento.id = None
        orchestrator.repo.create_evento.return_value = 1
        orchestrator.calendar.create_event.side_effect = RuntimeError("Calendar error")

        result = await orchestrator.save_confirmed_event(sample_evento, sample_cliente)
        assert result.status == ResultStatus.ERROR
        assert "Calendar" in result.message
        orchestrator.repo.delete_evento.assert_awaited_once_with(1)


# ── Edición de evento ─────────────────────────────────────────────────────────


class TestEditEventFromText:
    """Tests para edit_event_from_text()."""

    async def test_cambios_detectados(self, orchestrator, mock_parser, sample_evento):
        """Si el parser detecta cambios, devuelve success con dict."""
        mock_parser.parse_edit_event.return_value = ParsedEdit(
            changes={"notas": "nuevo valor"},
        )
        result = await orchestrator.edit_event_from_text(
            "cambiar notas a nuevo valor", sample_evento, 123
        )
        assert result.ok
        assert result.data == {"notas": "nuevo valor"}

    async def test_sin_cambios_pide_clarificacion(
        self, orchestrator, mock_parser, sample_evento
    ):
        """Si no detecta cambios, pide clarificación."""
        mock_parser.parse_edit_event.return_value = ParsedEdit(changes={})
        result = await orchestrator.edit_event_from_text("no sé", sample_evento, 123)
        assert result.status == ResultStatus.NEEDS_INPUT

    async def test_parser_pide_clarificacion(
        self, orchestrator, mock_parser, sample_evento
    ):
        """Si el parser tiene pregunta de clarificación, la propaga."""
        mock_parser.parse_edit_event.return_value = ParsedEdit(
            clarification_question="¿Qué campo querés cambiar?",
        )
        result = await orchestrator.edit_event_from_text("editar", sample_evento, 123)
        assert result.status == ResultStatus.NEEDS_INPUT
        assert "campo" in result.question


# ── Apply event changes ───────────────────────────────────────────────────────


class TestApplyEventChanges:
    """Tests para apply_event_changes()."""

    async def test_actualiza_bd_y_calendar(self, orchestrator, sample_evento):
        """Actualiza en BD y sincroniza Calendar."""
        orchestrator.repo.get_evento_by_id.return_value = sample_evento

        result = await orchestrator.apply_event_changes(1, {"notas": "nueva nota"})
        assert result.ok
        orchestrator.repo.update_evento.assert_awaited()
        orchestrator.calendar.update_event.assert_awaited()

    async def test_evento_no_encontrado(self, orchestrator):
        """Si el evento no existe, devuelve error."""
        orchestrator.repo.get_evento_by_id.return_value = None
        result = await orchestrator.apply_event_changes(999, {"notas": "x"})
        assert result.status == ResultStatus.ERROR
        assert "no encontrado" in result.message.lower()

    async def test_sin_cambios_validos(self, orchestrator, sample_evento):
        """Si los cambios no son válidos, devuelve error."""
        orchestrator.repo.get_evento_by_id.return_value = sample_evento
        result = await orchestrator.apply_event_changes(1, {"campo_inexistente": "x"})
        assert result.status == ResultStatus.ERROR

    async def test_rollback_si_calendar_falla(self, orchestrator, sample_evento):
        """Si Calendar falla al actualizar, hace rollback de BD."""
        orchestrator.repo.get_evento_by_id.return_value = sample_evento
        orchestrator.calendar.update_event.side_effect = RuntimeError("Calendar down")

        result = await orchestrator.apply_event_changes(1, {"notas": "nueva nota"})
        assert result.status == ResultStatus.ERROR
        # Debe haber hecho rollback (update_evento llamado 2 veces: original + rollback)
        assert orchestrator.repo.update_evento.await_count == 2


# ── Eliminación de evento ─────────────────────────────────────────────────────


class TestDeleteEvent:
    """Tests para delete_event()."""

    async def test_eliminar_completo_calendar_y_bd(self, orchestrator, sample_evento):
        """Elimina de Calendar y luego de BD."""
        orchestrator.repo.get_evento_by_id.return_value = sample_evento

        result = await orchestrator.delete_event(1)
        assert result.ok
        orchestrator.calendar.delete_event.assert_awaited_once_with("google_evt_123")
        orchestrator.repo.delete_evento.assert_awaited_once_with(1)

    async def test_evento_sin_google_id(self, orchestrator, sample_evento):
        """Si no tiene google_event_id, solo elimina de BD."""
        sample_evento.google_event_id = None
        orchestrator.repo.get_evento_by_id.return_value = sample_evento

        result = await orchestrator.delete_event(1)
        assert result.ok
        orchestrator.calendar.delete_event.assert_not_awaited()
        orchestrator.repo.delete_evento.assert_awaited_once()

    async def test_evento_no_encontrado(self, orchestrator):
        """Si el evento no existe, devuelve error."""
        orchestrator.repo.get_evento_by_id.return_value = None
        result = await orchestrator.delete_event(999)
        assert result.status == ResultStatus.ERROR

    async def test_calendar_falla_marca_cancelado(self, orchestrator, sample_evento):
        """Si Calendar falla, marca como cancelado en BD en vez de eliminar."""
        orchestrator.repo.get_evento_by_id.return_value = sample_evento
        orchestrator.calendar.delete_event.side_effect = RuntimeError("Calendar error")

        result = await orchestrator.delete_event(1)
        assert result.ok
        assert "cancelado" in result.message.lower()
        orchestrator.repo.update_evento.assert_awaited_once()


# ── Cierre de servicio ────────────────────────────────────────────────────────


class TestParseClosureText:
    """Tests para parse_closure_text()."""

    async def test_parseo_exitoso(self, orchestrator, mock_parser):
        """Datos de cierre parseados correctamente."""
        mock_parser.parse_closure.return_value = ParsedClosure(
            trabajo_realizado="Instalación completa",
            monto_cobrado=5000.0,
            notas_cierre="Todo OK",
        )
        result = await orchestrator.parse_closure_text("Instalé todo, cobré 5000")
        assert result.ok
        assert result.data["trabajo_realizado"] == "Instalación completa"
        assert result.data["monto_cobrado"] == 5000.0

    async def test_sin_datos_pide_info(self, orchestrator, mock_parser):
        """Si no hay datos de cierre, pide información."""
        mock_parser.parse_closure.return_value = ParsedClosure()
        result = await orchestrator.parse_closure_text("nada")
        assert result.status == ResultStatus.NEEDS_INPUT

    async def test_parser_pide_clarificacion(self, orchestrator, mock_parser):
        """Si el parser tiene pregunta, la propaga."""
        mock_parser.parse_closure.return_value = ParsedClosure(
            clarification_question="¿Cuánto cobraste?",
        )
        result = await orchestrator.parse_closure_text("terminé")
        assert result.status == ResultStatus.NEEDS_INPUT
        assert "cobraste" in result.question.lower()


class TestCompleteEvent:
    """Tests para complete_event()."""

    async def test_completar_bd_y_calendar(
        self, orchestrator, sample_evento, sample_cliente
    ):
        """Actualiza BD y Calendar con datos de cierre."""
        orchestrator.repo.get_evento_by_id.return_value = sample_evento
        orchestrator.repo.get_cliente_by_id.return_value = sample_cliente

        closure_data = {
            "trabajo_realizado": "Instalación",
            "monto_cobrado": 5000,
        }
        result = await orchestrator.complete_event(1, closure_data)
        assert result.ok
        orchestrator.repo.complete_evento.assert_awaited_once()
        orchestrator.calendar.complete_event.assert_awaited_once()

    async def test_evento_no_encontrado(self, orchestrator):
        """Si el evento no existe, devuelve error."""
        orchestrator.repo.get_evento_by_id.return_value = None
        result = await orchestrator.complete_event(999, {})
        assert result.status == ResultStatus.ERROR

    async def test_calendar_falla_bd_no_revierte(
        self, orchestrator, sample_evento, sample_cliente
    ):
        """Si Calendar falla, la BD NO revierte (decisión de diseño)."""
        orchestrator.repo.get_evento_by_id.return_value = sample_evento
        orchestrator.repo.get_cliente_by_id.return_value = sample_cliente
        orchestrator.calendar.complete_event.side_effect = RuntimeError("Calendar down")

        result = await orchestrator.complete_event(1, {"trabajo_realizado": "Algo"})
        # El resultado sigue siendo OK (BD se actualizó)
        assert result.ok
        orchestrator.repo.complete_evento.assert_awaited_once()


# ── Listados ──────────────────────────────────────────────────────────────────


class TestListados:
    """Tests para list_pending_events, list_today_events, list_contacts."""

    async def test_list_pending_events(self, orchestrator, sample_evento):
        """Delega a repo.list_eventos_pendientes()."""
        orchestrator.repo.list_eventos_pendientes.return_value = [sample_evento]
        result = await orchestrator.list_pending_events()
        assert len(result) == 1
        assert result[0].id == sample_evento.id

    async def test_list_today_events(self, orchestrator):
        """Delega a repo.list_eventos_hoy()."""
        orchestrator.repo.list_eventos_hoy.return_value = []
        result = await orchestrator.list_today_events()
        assert result == []

    async def test_list_contacts(self, orchestrator, sample_cliente):
        """Delega a repo.list_clientes()."""
        orchestrator.repo.list_clientes.return_value = [sample_cliente]
        result = await orchestrator.list_contacts()
        assert len(result) == 1


# ── Mensajes naturales ────────────────────────────────────────────────────────


class TestHandleNaturalMessage:
    """Tests para handle_natural_message()."""

    async def test_saludo(self, orchestrator, mock_parser):
        """Intent SALUDO devuelve mensaje de bienvenida."""
        mock_parser.detect_intent.return_value = IntentDetection(
            intent=Intent.SALUDO,
            confidence=1.0,
        )
        result = await orchestrator.handle_natural_message("hola", 123)
        assert result.ok
        assert "hola" in result.message.lower()

    async def test_ayuda(self, orchestrator, mock_parser):
        """Intent AYUDA devuelve mensaje de ayuda."""
        mock_parser.detect_intent.return_value = IntentDetection(
            intent=Intent.AYUDA,
            confidence=1.0,
        )
        result = await orchestrator.handle_natural_message("ayuda", 123)
        assert result.ok
        assert "menu" in result.message.lower() or "opciones" in result.message.lower()

    async def test_desconocido(self, orchestrator, mock_parser):
        """Intent DESCONOCIDO devuelve needs_clarification."""
        mock_parser.detect_intent.return_value = IntentDetection(
            intent=Intent.DESCONOCIDO,
            confidence=0.5,
        )
        result = await orchestrator.handle_natural_message("asdf", 123)
        assert result.status == ResultStatus.NEEDS_INPUT

    async def test_ver_eventos_delega(self, orchestrator, mock_parser, sample_evento):
        """Intent VER_EVENTOS lista los eventos pendientes."""
        mock_parser.detect_intent.return_value = IntentDetection(
            intent=Intent.VER_EVENTOS,
            confidence=1.0,
        )
        orchestrator.repo.list_eventos_pendientes.return_value = [sample_evento]

        result = await orchestrator.handle_natural_message("ver turnos", 123)
        assert result.ok
        assert result.data["action"] == "ver_eventos"
        assert len(result.data["eventos"]) == 1

    async def test_crear_evento_retorna_action(self, orchestrator, mock_parser):
        """Intent CREAR_EVENTO retorna action para que el bot inicie el flujo."""
        mock_parser.detect_intent.return_value = IntentDetection(
            intent=Intent.CREAR_EVENTO,
            confidence=1.0,
        )

        result = await orchestrator.handle_natural_message("turno para Juan", 123)
        assert result.ok
        assert result.data["action"] == "crear_evento"
        assert result.data["original_text"] == "turno para Juan"

    async def test_eliminar_delega(self, orchestrator, mock_parser):
        """Intent ELIMINAR_EVENTO lista eventos para seleccionar."""
        mock_parser.detect_intent.return_value = IntentDetection(
            intent=Intent.ELIMINAR_EVENTO,
            confidence=1.0,
        )
        orchestrator.repo.list_eventos_pendientes.return_value = []

        result = await orchestrator.handle_natural_message("borrar turno", 123)
        assert result.ok
        assert result.data["action"] == "eliminar"

    async def test_error_generico(self, orchestrator, mock_parser):
        """Si el parser explota, devuelve error."""
        mock_parser.detect_intent.side_effect = RuntimeError("LLM down")
        result = await orchestrator.handle_natural_message("algo", 123)
        assert result.status == ResultStatus.ERROR


# ── Disponibilidad ────────────────────────────────────────────────────────────


class TestCheckAvailability:
    """Tests para _check_availability()."""

    async def test_sin_eventos_disponible(self, orchestrator):
        """Sin eventos, el horario está libre."""
        orchestrator.repo.list_eventos_by_date.return_value = []
        result = await orchestrator._check_availability(
            date(2026, 3, 15), time(16, 0), 60
        )
        assert result is None

    async def test_conflicto_solapamiento(self, orchestrator):
        """Un evento que se superpone devuelve info del conflicto."""
        existing = Evento(
            id=1,
            cliente_id=1,
            tipo_servicio=TipoServicio.OTRO,
            fecha_hora=datetime(2026, 3, 15, 16, 0, tzinfo=TIMEZONE),
            duracion_minutos=60,
        )
        orchestrator.repo.list_eventos_by_date.return_value = [existing]

        result = await orchestrator._check_availability(
            date(2026, 3, 15), time(16, 0), 60
        )
        assert result is not None
        assert "16:00" in result

    async def test_consecutivos_permitidos(self, orchestrator):
        """Un evento que termina a las 16:00 NO bloquea el slot de 16:00."""
        existing = Evento(
            id=1,
            cliente_id=1,
            tipo_servicio=TipoServicio.OTRO,
            fecha_hora=datetime(2026, 3, 15, 15, 0, tzinfo=TIMEZONE),
            duracion_minutos=60,
        )
        orchestrator.repo.list_eventos_by_date.return_value = [existing]

        # Evento nuevo a las 16:00 — no se superpone con 15:00-16:00
        result = await orchestrator._check_availability(
            date(2026, 3, 15), time(16, 0), 60
        )
        assert result is None

    async def test_eventos_cancelados_ignorados(self, orchestrator):
        """Eventos cancelados no bloquean el horario."""
        cancelled = Evento(
            id=1,
            cliente_id=1,
            tipo_servicio=TipoServicio.OTRO,
            fecha_hora=datetime(2026, 3, 15, 16, 0, tzinfo=TIMEZONE),
            duracion_minutos=60,
            estado=EstadoEvento.CANCELADO,
        )
        orchestrator.repo.list_eventos_by_date.return_value = [cancelled]

        result = await orchestrator._check_availability(
            date(2026, 3, 15), time(16, 0), 60
        )
        assert result is None

    async def test_eventos_completados_ignorados(self, orchestrator):
        """Eventos completados no bloquean el horario."""
        completed = Evento(
            id=1,
            cliente_id=1,
            tipo_servicio=TipoServicio.OTRO,
            fecha_hora=datetime(2026, 3, 15, 16, 0, tzinfo=TIMEZONE),
            duracion_minutos=60,
            estado=EstadoEvento.COMPLETADO,
        )
        orchestrator.repo.list_eventos_by_date.return_value = [completed]

        result = await orchestrator._check_availability(
            date(2026, 3, 15), time(16, 0), 60
        )
        assert result is None


# ── Slots disponibles ─────────────────────────────────────────────────────────


class TestGetAvailableSlots:
    """Tests para _get_available_slots()."""

    async def test_domingo_sin_slots(self, orchestrator):
        """El domingo no hay slots."""
        # 2026-03-08 es un domingo
        sunday = date(2026, 3, 8)
        assert sunday.weekday() == 6
        slots = await orchestrator._get_available_slots(sunday)
        assert slots == []

    async def test_dia_libre_todos_los_slots(self, orchestrator):
        """Un día sin eventos tiene todos los slots del horario laboral."""
        # 2026-03-09 es lunes (weekday 0)
        monday = date(2026, 3, 9)
        assert monday.weekday() == 0
        orchestrator.repo.list_eventos_by_date.return_value = []

        slots = await orchestrator._get_available_slots(monday)
        # Horario 15:00-21:00 = 6 slots de 1h
        assert len(slots) == 6
        assert slots[0].start == time(15, 0)
        assert slots[-1].end == time(21, 0)

    async def test_evento_bloquea_slot(self, orchestrator):
        """Un evento a las 16:00 bloquea ese slot."""
        monday = date(2026, 3, 9)
        existing = Evento(
            id=1,
            cliente_id=1,
            tipo_servicio=TipoServicio.OTRO,
            fecha_hora=datetime(2026, 3, 9, 16, 0, tzinfo=TIMEZONE),
            duracion_minutos=60,
        )
        orchestrator.repo.list_eventos_by_date.return_value = [existing]

        slots = await orchestrator._get_available_slots(monday)
        # 6 slots - 1 bloqueado = 5
        assert len(slots) == 5
        # El slot 16:00-17:00 NO está
        slot_starts = [s.start for s in slots]
        assert time(16, 0) not in slot_starts

    async def test_consecutivos_permitidos_en_slots(self, orchestrator):
        """Un evento 15:00-16:00 deja disponible el slot 16:00-17:00."""
        monday = date(2026, 3, 9)
        existing = Evento(
            id=1,
            cliente_id=1,
            tipo_servicio=TipoServicio.OTRO,
            fecha_hora=datetime(2026, 3, 9, 15, 0, tzinfo=TIMEZONE),
            duracion_minutos=60,
        )
        orchestrator.repo.list_eventos_by_date.return_value = [existing]

        slots = await orchestrator._get_available_slots(monday)
        slot_starts = [s.start for s in slots]
        assert time(16, 0) in slot_starts  # Consecutivo OK

    async def test_sabado_horario_diferente(self, orchestrator):
        """Sábado usa horario 08:00-20:00 = 12 slots."""
        saturday = date(2026, 3, 7)
        assert saturday.weekday() == 5
        orchestrator.repo.list_eventos_by_date.return_value = []

        slots = await orchestrator._get_available_slots(saturday)
        assert len(slots) == 12
        assert slots[0].start == time(8, 0)
        assert slots[-1].end == time(20, 0)


# ── Resolución de cliente ─────────────────────────────────────────────────────


class TestResolveCliente:
    """Tests para _resolve_cliente()."""

    async def test_busca_por_telefono_primero(self, orchestrator, sample_cliente):
        """Si hay teléfono y existe, devuelve el cliente existente."""
        orchestrator.repo.get_cliente_by_telefono.return_value = sample_cliente
        parsed = ParsedEvent(
            cliente_nombre="Juan",
            cliente_telefono="+5491155551234",
            fecha=date(2026, 3, 15),
            hora=time(16, 0),
        )
        result = await orchestrator._resolve_cliente(parsed)
        assert result.id == sample_cliente.id

    async def test_busca_por_nombre_si_no_hay_telefono(
        self, orchestrator, sample_cliente
    ):
        """Sin teléfono, busca por nombre fuzzy."""
        orchestrator.repo.search_clientes_fuzzy.return_value = [(sample_cliente, 90)]
        parsed = ParsedEvent(
            cliente_nombre="Juan Perez",
            fecha=date(2026, 3, 15),
            hora=time(16, 0),
        )
        result = await orchestrator._resolve_cliente(parsed)
        assert result.id == sample_cliente.id

    async def test_crea_nuevo_si_no_existe(self, orchestrator):
        """Si no hay match, crea un cliente nuevo."""
        orchestrator.repo.get_cliente_by_telefono.return_value = None
        orchestrator.repo.search_clientes_fuzzy.return_value = []
        orchestrator.repo.create_cliente.return_value = 42

        parsed = ParsedEvent(
            cliente_nombre="Nuevo Cliente",
            cliente_telefono="+5491199998888",
            fecha=date(2026, 3, 15),
            hora=time(16, 0),
        )
        result = await orchestrator._resolve_cliente(parsed)
        assert result.id == 42
        orchestrator.repo.create_cliente.assert_awaited_once()

    async def test_sin_nombre_ni_telefono_crea_sin_nombre(self, orchestrator):
        """Sin nombre ni teléfono, crea 'Cliente sin nombre'."""
        orchestrator.repo.search_clientes_fuzzy.return_value = []
        orchestrator.repo.create_cliente.return_value = 43

        parsed = ParsedEvent(
            fecha=date(2026, 3, 15),
            hora=time(16, 0),
        )
        result = await orchestrator._resolve_cliente(parsed)
        assert result.nombre == "Cliente sin nombre"
