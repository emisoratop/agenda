# tests/integration/test_complete_event.py
"""Test de integración E2E: flujo de cierre de servicio.

Usa BD real (SQLite en memoria) + Repository real.
Calendar y LLM están mockeados (servicios externos).
"""

from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import aiosqlite
import pytest

from src.core.result import ResultStatus
from src.db.models import (
    Cliente,
    EstadoEvento,
    Evento,
    TipoServicio,
)
from src.db.repository import Repository
from src.llm.schemas import ParsedClosure
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
    cal.create_event = AsyncMock(return_value="google_evt_456")
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


@pytest.fixture
async def evento_pendiente(repo):
    """Crea un cliente + evento pendiente en la BD y los retorna."""
    cliente = Cliente(
        nombre="Carlos Test",
        telefono="+5491177778888",
        direccion="Calle Test 456",
    )
    cid = await repo.create_cliente(cliente)
    cliente.id = cid

    tomorrow = datetime.now(TIMEZONE).date() + timedelta(days=1)
    evento = Evento(
        cliente_id=cid,
        google_event_id="google_evt_existing",
        tipo_servicio=TipoServicio.INSTALACION,
        fecha_hora=datetime.combine(tomorrow, time(16, 0), tzinfo=TIMEZONE),
        duracion_minutos=60,
        notas="Instalar equipo",
    )
    eid = await repo.create_evento(evento)
    evento.id = eid

    return evento, cliente


# ── Tests E2E ─────────────────────────────────────────────────────────────────


class TestCompleteEventE2E:
    """Flujo completo: parsear cierre → actualizar BD → actualizar Calendar."""

    async def test_flujo_completo_cierre(
        self, orchestrator, mock_parser, mock_calendar, repo, evento_pendiente
    ):
        """Cierra un evento: parsea datos → BD completado → Calendar verde."""
        evento, cliente = evento_pendiente

        # Paso 1: parsear datos de cierre
        mock_parser.parse_closure.return_value = ParsedClosure(
            trabajo_realizado="Instalación de split 3000 frigorías",
            monto_cobrado=15000.0,
            notas_cierre="Cliente satisfecho, quedó andando perfecto",
        )
        parse_result = await orchestrator.parse_closure_text(
            "Instalé split 3000 frigorías, cobré 15000, todo OK"
        )
        assert parse_result.ok
        closure_data = parse_result.data
        assert (
            closure_data["trabajo_realizado"] == "Instalación de split 3000 frigorías"
        )
        assert closure_data["monto_cobrado"] == 15000.0

        # Paso 2: completar evento
        complete_result = await orchestrator.complete_event(evento.id, closure_data)
        assert complete_result.ok

        # Verificar BD: estado=completado + datos de cierre
        db_evento = await repo.get_evento_by_id(evento.id)
        assert db_evento is not None
        assert db_evento.estado == EstadoEvento.COMPLETADO
        assert db_evento.trabajo_realizado == "Instalación de split 3000 frigorías"
        assert db_evento.monto_cobrado == 15000.0
        assert db_evento.notas_cierre == "Cliente satisfecho, quedó andando perfecto"

        # Verificar Calendar: se llamó a complete_event con color verde
        mock_calendar.complete_event.assert_awaited_once()
        call_args = mock_calendar.complete_event.call_args
        assert call_args[0][0] == "google_evt_existing"  # google_event_id

    async def test_cierre_sin_google_event_id(self, orchestrator, repo):
        """Si el evento no tiene google_event_id, solo actualiza BD."""
        # Crear evento SIN google_event_id
        cliente = Cliente(nombre="Test Sin GCal", telefono="+5491100000001")
        cid = await repo.create_cliente(cliente)
        tomorrow = datetime.now(TIMEZONE).date() + timedelta(days=1)
        evento = Evento(
            cliente_id=cid,
            tipo_servicio=TipoServicio.OTRO,
            fecha_hora=datetime.combine(tomorrow, time(17, 0), tzinfo=TIMEZONE),
            duracion_minutos=60,
        )
        eid = await repo.create_evento(evento)

        closure_data = {"trabajo_realizado": "Revisión general", "monto_cobrado": 5000}
        result = await orchestrator.complete_event(eid, closure_data)
        assert result.ok

        # BD actualizada correctamente
        db_evento = await repo.get_evento_by_id(eid)
        assert db_evento.estado == EstadoEvento.COMPLETADO
        assert db_evento.trabajo_realizado == "Revisión general"

    async def test_cierre_calendar_falla_bd_persiste(
        self, orchestrator, mock_calendar, repo, evento_pendiente
    ):
        """Si Calendar falla al completar, BD NO revierte (decisión de diseño)."""
        evento, _ = evento_pendiente
        mock_calendar.complete_event.side_effect = RuntimeError("Calendar error")

        closure_data = {"trabajo_realizado": "Reparación", "monto_cobrado": 8000}
        result = await orchestrator.complete_event(evento.id, closure_data)

        # Resultado OK (BD se actualizó aunque Calendar falló)
        assert result.ok

        # BD sí quedó como completado
        db_evento = await repo.get_evento_by_id(evento.id)
        assert db_evento.estado == EstadoEvento.COMPLETADO
        assert db_evento.trabajo_realizado == "Reparación"

    async def test_cierre_evento_no_existente(self, orchestrator):
        """Completar un evento inexistente devuelve error."""
        result = await orchestrator.complete_event(9999, {"trabajo_realizado": "X"})
        assert result.status == ResultStatus.ERROR
        assert "no encontrado" in result.message.lower()

    async def test_evento_completado_no_bloquea_horario(
        self, orchestrator, repo, evento_pendiente
    ):
        """Una vez completado, el evento ya no bloquea el horario."""
        evento, _ = evento_pendiente

        # Completar el evento
        await orchestrator.complete_event(evento.id, {"trabajo_realizado": "Hecho"})

        # Verificar que el horario está libre
        conflict = await orchestrator._check_availability(
            evento.fecha_hora.date(),
            evento.fecha_hora.time(),
            60,
        )
        assert conflict is None  # No hay conflicto

    async def test_parse_closure_sin_datos_pide_info(self, orchestrator, mock_parser):
        """Si el parser no extrae datos, pide información."""
        mock_parser.parse_closure.return_value = ParsedClosure()
        result = await orchestrator.parse_closure_text("nada")
        assert result.status == ResultStatus.NEEDS_INPUT
        assert "trabajo" in result.question.lower() or "cobr" in result.question.lower()

    async def test_parse_closure_con_clarificacion(self, orchestrator, mock_parser):
        """Si el parser tiene pregunta de clarificación, la propaga."""
        mock_parser.parse_closure.return_value = ParsedClosure(
            clarification_question="¿Cuánto cobraste?",
        )
        result = await orchestrator.parse_closure_text("terminé el trabajo")
        assert result.status == ResultStatus.NEEDS_INPUT
        assert "cobraste" in result.question.lower()

    async def test_flujo_cierre_solo_trabajo_sin_monto(
        self, orchestrator, mock_parser, repo, evento_pendiente
    ):
        """Se puede completar solo con trabajo_realizado, sin monto."""
        evento, _ = evento_pendiente

        mock_parser.parse_closure.return_value = ParsedClosure(
            trabajo_realizado="Revisión preventiva",
        )
        parse_result = await orchestrator.parse_closure_text("Hice revisión preventiva")
        assert parse_result.ok
        assert "monto_cobrado" not in parse_result.data

        complete_result = await orchestrator.complete_event(
            evento.id, parse_result.data
        )
        assert complete_result.ok

        db_evento = await repo.get_evento_by_id(evento.id)
        assert db_evento.estado == EstadoEvento.COMPLETADO
        assert db_evento.trabajo_realizado == "Revisión preventiva"
        assert db_evento.monto_cobrado is None
