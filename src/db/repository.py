# src/db/repository.py
"""Repository: capa de acceso a datos con CRUD asincrónico completo."""

import json
import logging
from datetime import date, datetime
from typing import Optional

import aiosqlite
from thefuzz import fuzz, process

from src.core.exceptions import (
    ClienteNotFoundError,
    DatabaseError,
    DuplicateClienteError,
    EventoNotFoundError,
)
from src.db.cache import TTLCache
from src.db.models import Cliente, EstadoEvento, Evento, UsuarioAutorizado

logger = logging.getLogger(__name__)


class Repository:
    """Repositorio unificado de acceso a datos."""

    # Whitelists de campos actualizables (previene SQL injection vía kwargs keys)
    _CLIENTE_UPDATABLE = frozenset({"nombre", "telefono", "direccion", "notas"})
    _EVENTO_UPDATABLE = frozenset(
        {
            "google_event_id",
            "tipo_servicio",
            "prioridad",
            "fecha_hora",
            "duracion_minutos",
            "estado",
            "notas",
            "fotos",
        }
    )
    _CLOSURE_UPDATABLE = frozenset(
        {
            "trabajo_realizado",
            "monto_cobrado",
            "notas_cierre",
            "fotos",
        }
    )

    def __init__(self, db: aiosqlite.Connection, cache_ttl: int = 300):
        self._db = db
        self._cache = TTLCache(ttl_seconds=cache_ttl)

    # ── Clientes ──────────────────────────────

    async def create_cliente(self, cliente: Cliente) -> int:
        """Crea un cliente y devuelve su ID."""
        try:
            cursor = await self._db.execute(
                "INSERT INTO clientes (nombre, telefono, direccion, notas) VALUES (?, ?, ?, ?)",
                (cliente.nombre, cliente.telefono, cliente.direccion, cliente.notas),
            )
            await self._db.commit()
            self._cache.invalidate("clientes")
            logger.info(
                "Cliente creado: id=%d, nombre=%s", cursor.lastrowid, cliente.nombre
            )
            return cursor.lastrowid
        except aiosqlite.IntegrityError as e:
            if "UNIQUE" in str(e):
                raise DuplicateClienteError(
                    f"Ya existe un cliente con teléfono {cliente.telefono}"
                ) from e
            raise DatabaseError(f"Error al crear cliente: {e}") from e

    async def get_cliente_by_id(self, cliente_id: int) -> Optional[Cliente]:
        """Obtiene un cliente por su ID."""
        cursor = await self._db.execute(
            "SELECT * FROM clientes WHERE id = ?", (cliente_id,)
        )
        row = await cursor.fetchone()
        return Cliente(**dict(row)) if row else None

    async def get_cliente_by_telefono(self, telefono: str) -> Optional[Cliente]:
        """Obtiene un cliente por su teléfono."""
        cursor = await self._db.execute(
            "SELECT * FROM clientes WHERE telefono = ?", (telefono,)
        )
        row = await cursor.fetchone()
        return Cliente(**dict(row)) if row else None

    async def list_clientes(self) -> list[Cliente]:
        """Lista todos los clientes. Utiliza caché."""
        cached = self._cache.get("clientes")
        if cached is not None:
            return cached

        cursor = await self._db.execute("SELECT * FROM clientes ORDER BY nombre")
        rows = await cursor.fetchall()
        clientes = [Cliente(**dict(r)) for r in rows]
        self._cache.set("clientes", clientes)
        return clientes

    async def update_cliente(self, cliente_id: int, **kwargs) -> bool:
        """Actualiza campos de un cliente."""
        if not kwargs:
            return False
        invalid = set(kwargs) - self._CLIENTE_UPDATABLE
        if invalid:
            raise ValueError(f"Campos no permitidos para cliente: {invalid}")
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [cliente_id]
        cursor = await self._db.execute(
            f"UPDATE clientes SET {sets}, updated_at = datetime('now','localtime') WHERE id = ?",
            values,
        )
        await self._db.commit()
        self._cache.invalidate("clientes")
        return cursor.rowcount > 0

    async def search_clientes_fuzzy(
        self, query: str, threshold: int = 75, limit: int = 5
    ) -> list[tuple[Cliente, int]]:
        """Busca clientes por nombre con coincidencia aproximada.

        Args:
            query: Nombre a buscar.
            threshold: Puntaje mínimo de coincidencia (0-100).
            limit: Máximo de resultados a devolver.

        Returns:
            Lista de (Cliente, score) ordenada por score descendente.
        """
        clientes = await self.list_clientes()
        if not clientes:
            return []

        choices = {c.id: c.nombre for c in clientes}
        results = process.extract(
            query,
            choices,
            scorer=fuzz.token_sort_ratio,
            limit=limit,
        )

        matched = []
        clientes_by_id = {c.id: c for c in clientes}
        for nombre, score, client_id in results:
            if score >= threshold:
                matched.append((clientes_by_id[client_id], score))

        return matched

    # ── Eventos ───────────────────────────────

    async def create_evento(self, evento: Evento) -> int:
        """Crea un evento y devuelve su ID."""
        fotos_json = json.dumps(evento.fotos) if evento.fotos else None
        try:
            cursor = await self._db.execute(
                """INSERT INTO eventos
                (cliente_id, google_event_id, tipo_servicio, prioridad,
                 fecha_hora, duracion_minutos, estado, notas, fotos)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    evento.cliente_id,
                    evento.google_event_id,
                    evento.tipo_servicio.value,
                    evento.prioridad.value,
                    evento.fecha_hora.isoformat(),
                    evento.duracion_minutos,
                    evento.estado.value,
                    evento.notas,
                    fotos_json,
                ),
            )
            await self._db.commit()
            self._cache.invalidate_prefix("eventos")
            logger.info(
                "Evento creado: id=%d, cliente_id=%d",
                cursor.lastrowid,
                evento.cliente_id,
            )
            return cursor.lastrowid
        except aiosqlite.IntegrityError as e:
            raise DatabaseError(f"Error al crear evento: {e}") from e

    async def get_evento_by_id(self, evento_id: int) -> Optional[Evento]:
        """Obtiene un evento por su ID."""
        cursor = await self._db.execute(
            "SELECT * FROM eventos WHERE id = ?", (evento_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        # Deserializar fotos desde JSON
        if data.get("fotos"):
            data["fotos"] = json.loads(data["fotos"])
        return Evento(**data)

    async def list_eventos_pendientes(self) -> list[Evento]:
        """Lista todos los eventos pendientes ordenados por fecha."""
        cursor = await self._db.execute(
            """SELECT * FROM eventos
            WHERE estado = 'pendiente'
            ORDER BY fecha_hora ASC"""
        )
        rows = await cursor.fetchall()
        return [self._row_to_evento(r) for r in rows]

    async def list_eventos_hoy(self) -> list[Evento]:
        """Lista los eventos pendientes del día de hoy."""
        cursor = await self._db.execute(
            """SELECT * FROM eventos
            WHERE estado = 'pendiente'
            AND date(fecha_hora) = date('now', 'localtime')
            ORDER BY fecha_hora ASC"""
        )
        rows = await cursor.fetchall()
        return [self._row_to_evento(r) for r in rows]

    async def list_eventos_by_date(self, target_date: date) -> list[Evento]:
        """Lista eventos de una fecha específica."""
        cursor = await self._db.execute(
            """SELECT * FROM eventos
            WHERE date(fecha_hora) = ?
            ORDER BY fecha_hora ASC""",
            (target_date.isoformat(),),
        )
        rows = await cursor.fetchall()
        return [self._row_to_evento(r) for r in rows]

    async def update_evento(self, evento_id: int, **kwargs) -> bool:
        """Actualiza campos de un evento."""
        if not kwargs:
            return False
        invalid = set(kwargs) - self._EVENTO_UPDATABLE
        if invalid:
            raise ValueError(f"Campos no permitidos para evento: {invalid}")
        # Serializar campos especiales
        if "tipo_servicio" in kwargs and hasattr(kwargs["tipo_servicio"], "value"):
            kwargs["tipo_servicio"] = kwargs["tipo_servicio"].value
        if "estado" in kwargs and hasattr(kwargs["estado"], "value"):
            kwargs["estado"] = kwargs["estado"].value
        if "prioridad" in kwargs and hasattr(kwargs["prioridad"], "value"):
            kwargs["prioridad"] = kwargs["prioridad"].value
        if "fecha_hora" in kwargs and isinstance(kwargs["fecha_hora"], datetime):
            kwargs["fecha_hora"] = kwargs["fecha_hora"].isoformat()
        if "fotos" in kwargs and isinstance(kwargs["fotos"], list):
            kwargs["fotos"] = json.dumps(kwargs["fotos"])

        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [evento_id]
        cursor = await self._db.execute(
            f"UPDATE eventos SET {sets}, updated_at = datetime('now','localtime') WHERE id = ?",
            values,
        )
        await self._db.commit()
        self._cache.invalidate_prefix("eventos")
        return cursor.rowcount > 0

    async def complete_evento(self, evento_id: int, **closure_data) -> bool:
        """Marca un evento como completado con datos de cierre."""
        if closure_data:
            invalid = set(closure_data) - self._CLOSURE_UPDATABLE
            if invalid:
                raise ValueError(f"Campos no permitidos para cierre: {invalid}")
            # Serializar fotos a JSON string antes del binding SQL
            if "fotos" in closure_data and isinstance(closure_data["fotos"], list):
                closure_data["fotos"] = json.dumps(closure_data["fotos"])
            sets = ", ".join(f"{k} = ?" for k in closure_data)
            values = list(closure_data.values()) + [evento_id]
            cursor = await self._db.execute(
                f"""UPDATE eventos
                SET {sets}, estado = 'completado',
                    updated_at = datetime('now','localtime')
                WHERE id = ?""",
                values,
            )
        else:
            cursor = await self._db.execute(
                """UPDATE eventos
                SET estado = 'completado',
                    updated_at = datetime('now','localtime')
                WHERE id = ?""",
                (evento_id,),
            )
        await self._db.commit()
        self._cache.invalidate_prefix("eventos")
        return cursor.rowcount > 0

    async def delete_evento(self, evento_id: int) -> bool:
        """Elimina un evento por su ID."""
        cursor = await self._db.execute(
            "DELETE FROM eventos WHERE id = ?", (evento_id,)
        )
        await self._db.commit()
        self._cache.invalidate_prefix("eventos")
        return cursor.rowcount > 0

    # ── Helpers ───────────────────────────────

    @staticmethod
    def _row_to_evento(row: aiosqlite.Row) -> Evento:
        """Convierte un Row de SQLite a un Evento Pydantic."""
        data = dict(row)
        if data.get("fotos"):
            data["fotos"] = json.loads(data["fotos"])
        return Evento(**data)
