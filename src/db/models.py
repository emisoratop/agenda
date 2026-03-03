# src/db/models.py
"""Modelos Pydantic y Enums para las entidades del sistema."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class TipoServicio(str, Enum):
    """Tipos de servicio disponibles."""

    INSTALACION = "instalacion"
    REVISION = "revision"
    MANTENIMIENTO = "mantenimiento"
    REPARACION = "reparacion"
    PRESUPUESTO = "presupuesto"
    OTRO = "otro"


class Prioridad(str, Enum):
    """Prioridad del evento. Alta permite bypass de solapamiento."""

    NORMAL = "normal"
    ALTA = "alta"


class EstadoEvento(str, Enum):
    """Estados posibles de un evento."""

    PENDIENTE = "pendiente"
    COMPLETADO = "completado"
    CANCELADO = "cancelado"


class Rol(str, Enum):
    """Roles de usuario del sistema."""

    ADMIN = "admin"
    EDITOR = "editor"


class Cliente(BaseModel):
    """Modelo de cliente."""

    id: Optional[int] = None
    nombre: str = Field(..., min_length=1)
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    notas: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Evento(BaseModel):
    """Modelo de evento/turno."""

    id: Optional[int] = None
    cliente_id: int
    google_event_id: Optional[str] = None
    tipo_servicio: TipoServicio
    prioridad: Prioridad = Prioridad.NORMAL
    fecha_hora: datetime
    duracion_minutos: int = Field(default=60, ge=15, le=480)
    estado: EstadoEvento = EstadoEvento.PENDIENTE
    notas: Optional[str] = None
    trabajo_realizado: Optional[str] = None
    monto_cobrado: Optional[float] = Field(default=None, ge=0)
    notas_cierre: Optional[str] = None
    fotos: Optional[list[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def emoji(self) -> str:
        """Emoji representativo del tipo de servicio."""
        emojis = {
            TipoServicio.INSTALACION: "🔧",
            TipoServicio.REVISION: "🔍",
            TipoServicio.MANTENIMIENTO: "🛠️",
            TipoServicio.REPARACION: "⚡",
            TipoServicio.PRESUPUESTO: "📋",
            TipoServicio.OTRO: "📌",
        }
        return emojis.get(self.tipo_servicio, "📌")

    @property
    def hora_formateada(self) -> str:
        """Hora del evento formateada como HH:MM."""
        return self.fecha_hora.strftime("%H:%M")


class UsuarioAutorizado(BaseModel):
    """Modelo de usuario autorizado del sistema."""

    id: Optional[int] = None
    telegram_id: int
    nombre: Optional[str] = None
    rol: Rol
    activo: bool = True
    created_at: Optional[datetime] = None
