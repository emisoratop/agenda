# tests/unit/conftest.py
"""Fixtures compartidos para tests unitarios."""

import pytest
import aiosqlite

from src.db.models import Cliente, Evento, TipoServicio
from src.db.repository import Repository
from datetime import datetime


@pytest.fixture
async def db_connection():
    """Crea una conexión a BD en memoria con schema completo inicializado."""
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

        CREATE TABLE IF NOT EXISTS usuarios_autorizados (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id  INTEGER UNIQUE NOT NULL,
            nombre       TEXT,
            rol          TEXT    NOT NULL CHECK(rol IN ('admin','editor')),
            activo       INTEGER NOT NULL DEFAULT 1,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
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
    """Crea un Repository con la conexión de test."""
    return Repository(db_connection, cache_ttl=300)


@pytest.fixture
def sample_cliente():
    """Cliente de ejemplo."""
    return Cliente(
        nombre="Juan Pérez",
        telefono="+5491155551234",
        direccion="Av. Corrientes 1234",
        notas="Cliente regular",
    )


@pytest.fixture
def sample_evento():
    """Evento de ejemplo (requiere un cliente con id=1)."""
    return Evento(
        cliente_id=1,
        tipo_servicio=TipoServicio.INSTALACION,
        fecha_hora=datetime(2026, 3, 15, 10, 0),
        duracion_minutos=60,
        notas="Instalar aire acondicionado",
    )
