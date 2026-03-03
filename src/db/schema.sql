-- Schema de inicialización para el Agente Calendario
-- SQLite 3 con WAL mode

-- Habilitar WAL mode para mejor concurrencia
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

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
    fotos               TEXT,  -- JSON array de rutas
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

-- Índices para consultas frecuentes
CREATE INDEX IF NOT EXISTS idx_eventos_estado ON eventos(estado);
CREATE INDEX IF NOT EXISTS idx_eventos_fecha ON eventos(fecha_hora);
CREATE INDEX IF NOT EXISTS idx_eventos_cliente ON eventos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_clientes_nombre ON clientes(nombre);
