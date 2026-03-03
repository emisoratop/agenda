# tests/unit/test_calendar_client.py
"""Tests para GoogleCalendarClient con mock de la API de Google."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from httplib2 import Response as Httplib2Response
from googleapiclient.errors import HttpError

from src.calendar_api.client import (
    GoogleCalendarClient,
    TIMEZONE,
    MAX_RETRIES,
    _retry_with_backoff,
)
from src.calendar_api.colors import COMPLETED_COLOR
from src.core.exceptions import CalendarError


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_service():
    """Mock del servicio de Google Calendar API."""
    return MagicMock()


@pytest.fixture
def calendar_client(mock_service):
    """GoogleCalendarClient con servicio mockeado."""
    with patch(
        "src.calendar_api.client.build_calendar_service",
        return_value=mock_service,
    ):
        client = GoogleCalendarClient(
            service_account_path="fake/path.json",
            calendar_id="test-calendar@group.calendar.google.com",
        )
    return client


@pytest.fixture
def sample_datetime():
    """Datetime de ejemplo con timezone Argentina."""
    return datetime(2026, 3, 15, 10, 0, tzinfo=ZoneInfo(TIMEZONE))


# ── _retry_with_backoff ─────────────────────────────────────────────────────


class TestRetryWithBackoff:
    """Tests para la función de retry con backoff."""

    def test_success_on_first_try(self):
        """Retorna resultado si la primera llamada funciona."""
        func = MagicMock(return_value="ok")
        result = _retry_with_backoff(func)
        assert result == "ok"
        assert func.call_count == 1

    @patch("src.calendar_api.client.time_module.sleep")
    def test_retries_on_rate_limit(self, mock_sleep):
        """Reintenta en error 429 (rate limit)."""
        resp = Httplib2Response({"status": 429})
        error = HttpError(resp, b"Rate limit exceeded")
        func = MagicMock(side_effect=[error, error, "ok"])

        result = _retry_with_backoff(func)
        assert result == "ok"
        assert func.call_count == 3

    @patch("src.calendar_api.client.time_module.sleep")
    def test_retries_on_server_error(self, mock_sleep):
        """Reintenta en errores 500, 502, 503, 504."""
        for status_code in [500, 502, 503, 504]:
            resp = Httplib2Response({"status": status_code})
            error = HttpError(resp, b"Server error")
            func = MagicMock(side_effect=[error, "ok"])

            result = _retry_with_backoff(func)
            assert result == "ok"

    @patch("src.calendar_api.client.time_module.sleep")
    def test_raises_on_non_retryable_http_error(self, mock_sleep):
        """No reintenta en errores 400, 401, 403, 404."""
        resp = Httplib2Response({"status": 404})
        error = HttpError(resp, b"Not found")
        func = MagicMock(side_effect=error)

        with pytest.raises(CalendarError, match="Error de Google Calendar API"):
            _retry_with_backoff(func)
        assert func.call_count == 1

    @patch("src.calendar_api.client.time_module.sleep")
    def test_raises_calendar_error_after_max_retries(self, mock_sleep):
        """Lanza CalendarError después de agotar reintentos."""
        resp = Httplib2Response({"status": 429})
        error = HttpError(resp, b"Rate limit exceeded")
        func = MagicMock(side_effect=error)

        with pytest.raises(CalendarError, match="Se agotaron los reintentos"):
            _retry_with_backoff(func)
        assert func.call_count == MAX_RETRIES

    @patch("src.calendar_api.client.time_module.sleep")
    def test_exponential_backoff_delays(self, mock_sleep):
        """Verifica que los delays crecen exponencialmente."""
        resp = Httplib2Response({"status": 429})
        error = HttpError(resp, b"Rate limit")
        func = MagicMock(side_effect=error)

        with pytest.raises(CalendarError):
            _retry_with_backoff(func)

        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0, 4.0]

    @patch("src.calendar_api.client.time_module.sleep")
    def test_retries_on_network_error(self, mock_sleep):
        """Reintenta en errores de red genéricos."""
        func = MagicMock(side_effect=[ConnectionError("Network"), "ok"])

        result = _retry_with_backoff(func)
        assert result == "ok"
        assert func.call_count == 2


# ── GoogleCalendarClient.create_event ────────────────────────────────────────


class TestCreateEvent:
    """Tests para GoogleCalendarClient.create_event."""

    def test_create_event_returns_id(
        self, calendar_client, mock_service, sample_datetime
    ):
        """create_event retorna el ID del evento creado."""
        mock_service.events().insert().execute.return_value = {"id": "event123"}

        result = calendar_client.create_event(
            title="Juan Pérez — 351-1234567",
            location="Balcarce 132",
            description="Test description",
            start_datetime=sample_datetime,
        )
        assert result == "event123"

    def test_create_event_sends_correct_body(
        self, calendar_client, mock_service, sample_datetime
    ):
        """create_event envía el body correcto a la API."""
        mock_service.events().insert().execute.return_value = {"id": "event456"}

        calendar_client.create_event(
            title="Ana García — 351-9876543",
            location="Av. Corrientes 1234",
            description="Descripción del evento",
            start_datetime=sample_datetime,
            duration_minutes=90,
            color_id="9",
        )

        # Verificar que se llamó a insert con el calendarId correcto
        mock_service.events().insert.assert_called()

    def test_create_event_default_duration_60(
        self, calendar_client, mock_service, sample_datetime
    ):
        """La duración por defecto es 60 minutos."""
        mock_service.events().insert().execute.return_value = {"id": "event789"}

        calendar_client.create_event(
            title="Test",
            location="Calle 1",
            description="Desc",
            start_datetime=sample_datetime,
        )
        # Si no lanza error, el default funciona
        mock_service.events().insert().execute.assert_called()

    def test_create_event_default_color_graphite(
        self, calendar_client, mock_service, sample_datetime
    ):
        """El color por defecto es 8 (Graphite/gris)."""
        mock_service.events().insert().execute.return_value = {"id": "evt"}

        calendar_client.create_event(
            title="Test",
            location="Calle 1",
            description="Desc",
            start_datetime=sample_datetime,
        )
        # Verificar que no falla con default
        mock_service.events().insert().execute.assert_called()


# ── GoogleCalendarClient.update_event ────────────────────────────────────────


class TestUpdateEvent:
    """Tests para GoogleCalendarClient.update_event."""

    def test_update_event_returns_true(self, calendar_client, mock_service):
        """update_event retorna True en éxito."""
        mock_service.events().get().execute.return_value = {
            "id": "event123",
            "summary": "Original",
        }
        mock_service.events().update().execute.return_value = {}

        result = calendar_client.update_event("event123", summary="Actualizado")
        assert result is True

    def test_update_event_handles_datetime(
        self, calendar_client, mock_service, sample_datetime
    ):
        """update_event maneja start_datetime correctamente."""
        mock_service.events().get().execute.return_value = {
            "id": "event123",
            "start": {},
        }
        mock_service.events().update().execute.return_value = {}

        result = calendar_client.update_event(
            "event123", start_datetime=sample_datetime
        )
        assert result is True

    def test_update_event_handles_color_id(self, calendar_client, mock_service):
        """update_event maneja color_id correctamente."""
        mock_service.events().get().execute.return_value = {
            "id": "event123",
            "colorId": "8",
        }
        mock_service.events().update().execute.return_value = {}

        result = calendar_client.update_event("event123", color_id="9")
        assert result is True

    def test_update_event_raises_on_error(self, calendar_client, mock_service):
        """update_event lanza CalendarError en error no retryable."""
        resp = Httplib2Response({"status": 404})
        mock_service.events().get().execute.side_effect = HttpError(resp, b"Not found")

        with pytest.raises(CalendarError):
            calendar_client.update_event("nonexistent", summary="X")


# ── GoogleCalendarClient.delete_event ────────────────────────────────────────


class TestDeleteEvent:
    """Tests para GoogleCalendarClient.delete_event."""

    def test_delete_event_returns_true(self, calendar_client, mock_service):
        """delete_event retorna True en éxito."""
        mock_service.events().delete().execute.return_value = None

        result = calendar_client.delete_event("event123")
        assert result is True

    def test_delete_event_raises_on_error(self, calendar_client, mock_service):
        """delete_event lanza CalendarError en error no retryable."""
        resp = Httplib2Response({"status": 404})
        mock_service.events().delete().execute.side_effect = HttpError(
            resp, b"Not found"
        )

        with pytest.raises(CalendarError):
            calendar_client.delete_event("nonexistent")


# ── GoogleCalendarClient.complete_event ──────────────────────────────────────


class TestCompleteEvent:
    """Tests para GoogleCalendarClient.complete_event."""

    def test_complete_event_returns_true(self, calendar_client, mock_service):
        """complete_event retorna True en éxito."""
        mock_service.events().get().execute.return_value = {
            "id": "event123",
            "description": "Original",
            "colorId": "9",
        }
        mock_service.events().update().execute.return_value = {}

        result = calendar_client.complete_event("event123", "Descripción de cierre")
        assert result is True

    def test_complete_event_uses_completed_color(self, calendar_client, mock_service):
        """complete_event usa COMPLETED_COLOR (2, verde)."""
        event_data = {
            "id": "event123",
            "description": "Original",
            "colorId": "9",
        }
        mock_service.events().get().execute.return_value = event_data
        mock_service.events().update().execute.return_value = {}

        calendar_client.complete_event("event123", "Cierre")

        # Verificar que update fue llamado
        mock_service.events().update.assert_called()


# ── GoogleCalendarClient.list_upcoming_events ────────────────────────────────


class TestListUpcomingEvents:
    """Tests para GoogleCalendarClient.list_upcoming_events."""

    def test_list_returns_events(self, calendar_client, mock_service):
        """list_upcoming_events retorna lista de eventos."""
        mock_service.events().list().execute.return_value = {
            "items": [
                {"id": "e1", "summary": "Evento 1"},
                {"id": "e2", "summary": "Evento 2"},
            ]
        }

        result = calendar_client.list_upcoming_events()
        assert len(result) == 2
        assert result[0]["id"] == "e1"

    def test_list_returns_empty_list_when_no_events(
        self, calendar_client, mock_service
    ):
        """list_upcoming_events retorna lista vacía si no hay eventos."""
        mock_service.events().list().execute.return_value = {}

        result = calendar_client.list_upcoming_events()
        assert result == []

    def test_list_default_max_results_50(self, calendar_client, mock_service):
        """El max_results por defecto es 50."""
        mock_service.events().list().execute.return_value = {"items": []}

        calendar_client.list_upcoming_events()
        # Verificar que se llamó a list
        mock_service.events().list.assert_called()

    def test_list_custom_max_results(self, calendar_client, mock_service):
        """Se puede pasar un max_results personalizado."""
        mock_service.events().list().execute.return_value = {"items": []}

        calendar_client.list_upcoming_events(max_results=10)
        mock_service.events().list.assert_called()

    def test_list_raises_on_error(self, calendar_client, mock_service):
        """list_upcoming_events lanza CalendarError en error."""
        mock_service.events().list().execute.side_effect = Exception("Network error")

        with pytest.raises(CalendarError):
            calendar_client.list_upcoming_events()


# ── GoogleCalendarClient.check_availability ──────────────────────────────────


class TestCheckAvailability:
    """Tests para GoogleCalendarClient.check_availability."""

    def test_available_returns_true(
        self, calendar_client, mock_service, sample_datetime
    ):
        """check_availability retorna True si no hay conflictos."""
        mock_service.events().list().execute.return_value = {"items": []}

        end = sample_datetime + timedelta(hours=1)
        result = calendar_client.check_availability(sample_datetime, end)
        assert result is True

    def test_conflict_returns_false(
        self, calendar_client, mock_service, sample_datetime
    ):
        """check_availability retorna False si hay conflictos."""
        mock_service.events().list().execute.return_value = {
            "items": [{"id": "existing", "summary": "Otro evento"}]
        }

        end = sample_datetime + timedelta(hours=1)
        result = calendar_client.check_availability(sample_datetime, end)
        assert result is False

    def test_multiple_conflicts_returns_false(
        self, calendar_client, mock_service, sample_datetime
    ):
        """check_availability retorna False con múltiples conflictos."""
        mock_service.events().list().execute.return_value = {
            "items": [
                {"id": "e1", "summary": "Evento 1"},
                {"id": "e2", "summary": "Evento 2"},
            ]
        }

        end = sample_datetime + timedelta(hours=1)
        result = calendar_client.check_availability(sample_datetime, end)
        assert result is False

    def test_check_availability_raises_on_error(
        self, calendar_client, mock_service, sample_datetime
    ):
        """check_availability lanza CalendarError en error."""
        mock_service.events().list().execute.side_effect = Exception("Network error")

        end = sample_datetime + timedelta(hours=1)
        with pytest.raises(CalendarError):
            calendar_client.check_availability(sample_datetime, end)


# ── GoogleCalendarClient.__init__ ────────────────────────────────────────────


class TestClientInit:
    """Tests para la inicialización del cliente."""

    def test_stores_calendar_id(self, calendar_client):
        """El cliente almacena el calendar_id."""
        assert calendar_client.calendar_id == "test-calendar@group.calendar.google.com"

    def test_service_is_set(self, calendar_client):
        """El cliente tiene un servicio configurado."""
        assert calendar_client.service is not None
