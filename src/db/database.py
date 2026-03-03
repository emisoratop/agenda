# src/db/database.py
"""DatabaseManager: gestión de conexión, inicialización y migraciones SQLite."""

import logging
import os

import aiosqlite

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Gestiona la conexión a SQLite, inicialización de schema y migraciones."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> aiosqlite.Connection:
        """Abre la conexión a la BD y configura PRAGMAs de optimización."""
        # Crear directorio si no existe
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row

        # PRAGMAs de optimización
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._db.execute("PRAGMA cache_size=-8000")
        await self._db.execute("PRAGMA busy_timeout=5000")
        await self._db.execute("PRAGMA temp_store=MEMORY")

        logger.info("Conexión a SQLite establecida: %s", self.db_path)
        return self._db

    async def close(self) -> None:
        """Cierra la conexión a la BD."""
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("Conexión a SQLite cerrada")

    async def initialize(self) -> None:
        """Inicializa la BD ejecutando el schema SQL."""
        if not self._db:
            await self.connect()

        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        # Ejecutar cada statement por separado (PRAGMAs no van en executescript)
        for statement in schema_sql.split(";"):
            statement = statement.strip()
            if statement and not statement.startswith("--"):
                await self._db.execute(statement)
        await self._db.commit()

        logger.info("Schema de base de datos inicializado correctamente")

    async def run_migrations(self) -> None:
        """Ejecuta migraciones pendientes (placeholder para futuras versiones)."""
        if not self._db:
            await self.connect()

        # Crear tabla de control de versiones si no existe
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        await self._db.commit()

        # Consultar versión actual
        cursor = await self._db.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_version"
        )
        row = await cursor.fetchone()
        current_version = row[0] if row else 0
        logger.info("Versión actual del schema: %d", current_version)

    @property
    def db(self) -> aiosqlite.Connection:
        """Devuelve la conexión activa."""
        if not self._db:
            raise RuntimeError(
                "La base de datos no está conectada. Llamar a connect() primero."
            )
        return self._db

    async def __aenter__(self):
        await self.connect()
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
