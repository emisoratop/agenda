# tests/integration/test_create_event.py
"""Test de integración E2E: flujo de creación de evento.

Usa BD real (SQLite en memoria) + Repository real.
Calendar y LLM están mockeados (servicios externos).
"""

from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import aiosqlite
import pytest

from src.core.result import ResultStatus
from src.db.models import (
    Cliente,
    EstadoEvento,
    Evento,
    Prioridad,
    TipoServicio,
)
from src.db.repository import Repository
from src.llm.schemas import ParsedEvent
from src.orchestrator.orchestrator import Orchestrator

TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_connection():
    """BD en memoria con schema completo."""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")

    await db.executescript("""
        CREATE TABLE IF NOT EXISTS clientes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre      TEXT    NOT NULL,
            telefono    TEXT    UNIQUE,
            direccion   TEXT,
            notas       TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS eventos (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id          INTEGER NOT NULL REFERENCES clientes(id),
            google_event_id     TEXT    UNIQUE,
            tipo_servicio       TEXT    NOT NULL CHECK(tipo_servicio IN (
                                    'instalacion','revision','mantenimiento',
                                    'reparacion','presupuesto','otro'
                                )),
            prioridad           TEXT    NOT NULL DEFAULT 'normal' CHECK(prioridad IN (
                                    'normal','alta'
                                )),
            fecha_hora          TEXT    NOT NULL,
            duracion_minutos    INTEGER NOT NULL DEFAULT 60,
            estado              TEXT    NOT NULL DEFAULT 'pendiente' CHECK(estado IN (
                                    'pendiente','completado','cancelado'
                                )),
            notas               TEXT,
            trabajo_realizado   TEXT,
            monto_cobrado       REAL,
            notas_cierre        TEXT,
            fotos               TEXT,
            created_at          TEXT   NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at          TEXT   NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_eventos_estado ON eventos(estado);
        CREATE INDEX IF NOT EXISTS idx_eventos_fecha ON eventos(fecha_hora);
        CREATE INDEX IF NOT EXISTS idx_eventos_cliente ON eventos(cliente_id);
        CREATE INDEX IF NOT EXISTS idx_clientes_nombre ON clientes(nombre);
    """)
    await db.commit()

    yield db
    await db.close()


@pytest.fixture
async def repo(db_connection):
    """Repository real sobre BD en memoria."""
    return Repository(db_connection, cache_ttl=0)


@pytest.fixture
def mock_calendar():
    """Calendar mockeado."""
    cal = AsyncMock()
    cal.create_event = AsyncMock(return_value="google_evt_integration_123")
    cal.update_event = AsyncMock(return_value=True)
    cal.delete_event = AsyncMock(return_value=True)
    cal.complete_event = AsyncMock(return_value=True)
    return cal


@pytest.fixture
def mock_parser():
    """Parser mockeado."""
    return AsyncMock()


@pytest.fixture
def mock_settings():
    """Settings mockeado."""
    settings = MagicMock()
    settings.work_days_weekday_start = "15:00"
    settings.work_days_weekday_end = "21:00"
    settings.work_days_saturday_start = "08:00"
    settings.work_days_saturday_end = "20:00"
    return settings


@pytest.fixture
def orchestrator(repo, mock_calendar, mock_parser, mock_settings):
    """Orchestrator con BD real y Calendar/LLM mockeados."""
    return Orchestrator(
        repository=repo,
        calendar_client=mock_calendar,
        llm_parser=mock_parser,
        settings=mock_settings,
    )


def _next_weekday() -> date:
    """Devuelve la próxima fecha de lunes a viernes."""
    d = datetime.now(TIMEZONE).date() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


# ── Tests E2E ─────────────────────────────────────────────────────────────────


class TestCreateEventE2E:
    """Flujo completo: texto → parse → cliente → BD → Calendar."""

    async def test_flujo_completo_nuevo_cliente(
        self, orchestrator, mock_parser, mock_calendar, repo
    ):
        """Crea evento para un cliente nuevo: crea cliente + evento + calendar."""
        future = _next_weekday()
        mock_parser.parse_create_event.return_value = ParsedEvent(
            cliente_nombre="María García",
            cliente_telefono="+5491166667777",
            fecha=future,
            hora=time(16, 0),
            tipo_servicio=TipoServicio.INSTALACION,
            duracion_minutos=60,
            notas="Instalar split",
        )

        # Paso 1: create_event_from_text → prepara evento
        result = await orchestrator.create_event_from_text(
            "turno para María García tel 1166667777 instalación mañana 16hs", 123
        )
        assert result.ok, f"Error: {result.message}"

        evento = result.data["evento"]
        cliente = result.data["cliente"]

        # Verificar que el cliente se creó en BD
        assert cliente.id is not None
        db_cliente = await repo.get_cliente_by_telefono("+5491166667777")
        assert db_cliente is not None
        assert db_cliente.nombre == "María García"

        # Paso 2: save_confirmed_event → persiste en BD + Calendar
        save_result = await orchestrator.save_confirmed_event(evento, cliente)
        assert save_result.ok, f"Error save: {save_result.message}"

        # Verificar evento en BD
        saved_evento = save_result.data
        assert saved_evento.id is not None
        db_evento = await repo.get_evento_by_id(saved_evento.id)
        assert db_evento is not None
        assert db_evento.google_event_id == "google_evt_integration_123"
        assert db_evento.tipo_servicio == TipoServicio.INSTALACION
        assert db_evento.estado == EstadoEvento.PENDIENTE

        # Verificar que Calendar fue llamado
        mock_calendar.create_event.assert_awaited_once()

    async def test_flujo_cliente_existente(self, orchestrator, mock_parser, repo):
        """Si el cliente ya existe por teléfono, lo reutiliza."""
        # Crear cliente previo
        existing = Cliente(
            nombre="Pedro López",
            telefono="+5491188889999",
            direccion="Calle Falsa 123",
        )
        client_id = await repo.create_cliente(existing)

        future = _next_weekday()
        mock_parser.parse_create_event.return_value = ParsedEvent(
            cliente_nombre="Pedro",
            cliente_telefono="+5491188889999",
            fecha=future,
            hora=time(17, 0),
            tipo_servicio=TipoServicio.REVISION,
        )

        result = await orchestrator.create_event_from_text(
            "revisión Pedro tel 1188889999 mañana 17hs", 123
        )
        assert result.ok

        # No creó un cliente nuevo — reutilizó el existente
        cliente = result.data["cliente"]
        assert cliente.id == client_id
        assert cliente.nombre == "Pedro López"

    async def test_flujo_sin_fecha_pide_y_luego_completa(
        self, orchestrator, mock_parser, repo
    ):
        """Flujo de dos pasos: primero pide fecha, luego pide hora con slots."""
        # Paso 1: sin fecha
        mock_parser.parse_create_event.return_value = ParsedEvent(
            cliente_nombre="Ana",
        )
        result1 = await orchestrator.create_event_from_text("turno para Ana", 123)
        assert result1.status == ResultStatus.NEEDS_INPUT
        assert "fecha" in result1.question.lower()

        # Paso 2: con fecha pero sin hora → devuelve slots
        future = _next_weekday()
        mock_parser.parse_create_event.return_value = ParsedEvent(
            cliente_nombre="Ana",
            fecha=future,
            hora=None,
        )
        result2 = await orchestrator.create_event_from_text("para el lunes", 123)
        assert result2.status == ResultStatus.NEEDS_INPUT
        assert "available_slots" in result2.data

        # Paso 3: con fecha y hora → evento completo
        mock_parser.parse_create_event.return_value = ParsedEvent(
            cliente_nombre="Ana",
            fecha=future,
            hora=time(16, 0),
        )
        result3 = await orchestrator.create_event_from_text("a las 16", 123)
        assert result3.ok

    async def test_flujo_con_conflicto(self, orchestrator, mock_parser, repo):
        """Si hay conflicto de horario, devuelve CONFLICT con alternativas."""
        future = _next_weekday()

        # Crear un cliente y un evento existente en la BD
        existing_client = Cliente(nombre="ClienteX", telefono="+5491100001111")
        cid = await repo.create_cliente(existing_client)
        existing_evento = Evento(
            cliente_id=cid,
            tipo_servicio=TipoServicio.OTRO,
            fecha_hora=datetime.combine(future, time(16, 0), tzinfo=TIMEZONE),
            duracion_minutos=60,
        )
        await repo.create_evento(existing_evento)

        # Intentar crear otro evento a las 16:00
        mock_parser.parse_create_event.return_value = ParsedEvent(
            cliente_nombre="Nuevo",
            fecha=future,
            hora=time(16, 0),
        )
        result = await orchestrator.create_event_from_text(
            "turno Nuevo mañana 16hs", 123
        )
        assert result.status == ResultStatus.CONFLICT
        assert "available_slots" in result.data

    async def test_rollback_si_calendar_falla(
        self, orchestrator, mock_parser, mock_calendar, repo
    ):
        """Si Calendar falla al guardar, se elimina el evento de la BD."""
        future = _next_weekday()
        mock_parser.parse_create_event.return_value = ParsedEvent(
            cliente_nombre="TestRollback",
            fecha=future,
            hora=time(18, 0),
            tipo_servicio=TipoServicio.REPARACION,
        )

        # Paso 1: preparar evento
        result = await orchestrator.create_event_from_text("test", 123)
        assert result.ok

        # Paso 2: Calendar falla al guardar
        mock_calendar.create_event.side_effect = RuntimeError("Calendar error")
        save_result = await orchestrator.save_confirmed_event(
            result.data["evento"], result.data["cliente"]
        )
        assert save_result.status == ResultStatus.ERROR

        # Verificar que NO quedó evento huérfano en BD
        eventos = await repo.list_eventos_pendientes()
        assert len(eventos) == 0

    async def test_alta_prioridad_bypass_conflicto(
        self, orchestrator, mock_parser, repo
    ):
        """Prioridad alta permite crear aunque haya conflicto."""
        future = _next_weekday()

        # Crear evento existente
        client = Cliente(nombre="C1", telefono="+5491122223333")
        cid = await repo.create_cliente(client)
        existing = Evento(
            cliente_id=cid,
            tipo_servicio=TipoServicio.OTRO,
            fecha_hora=datetime.combine(future, time(16, 0), tzinfo=TIMEZONE),
            duracion_minutos=60,
        )
        await repo.create_evento(existing)

        # Crear evento urgente a las 16:00 (misma hora)
        mock_parser.parse_create_event.return_value = ParsedEvent(
            cliente_nombre="Urgente",
            fecha=future,
            hora=time(16, 0),
            prioridad=Prioridad.ALTA,
        )
        result = await orchestrator.create_event_from_text("urgente a las 16", 123)
        assert result.ok  # Bypass de conflicto

    async def test_consecutivos_permitidos(self, orchestrator, mock_parser, repo):
        """Un evento que termina a las 16:00 permite crear uno a las 16:00."""
        future = _next_weekday()

        # Evento existente 15:00-16:00
        client = Cliente(nombre="C2", telefono="+5491144445555")
        cid = await repo.create_cliente(client)
        existing = Evento(
            cliente_id=cid,
            tipo_servicio=TipoServicio.OTRO,
            fecha_hora=datetime.combine(future, time(15, 0), tzinfo=TIMEZONE),
            duracion_minutos=60,
        )
        await repo.create_evento(existing)

        # Crear evento a las 16:00 (consecutivo)
        mock_parser.parse_create_event.return_value = ParsedEvent(
            cliente_nombre="Consecutivo",
            fecha=future,
            hora=time(16, 0),
        )
        result = await orchestrator.create_event_from_text("turno a las 16", 123)
        assert result.ok  # Consecutivo permitido
