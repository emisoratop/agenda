# tests/unit/test_models.py
"""Tests para los modelos Pydantic y Enums."""

import pytest
from datetime import datetime
from src.db.models import (
    Cliente,
    EstadoEvento,
    Evento,
    Prioridad,
    Rol,
    TipoServicio,
    UsuarioAutorizado,
)


class TestEnums:
    """Tests para los enums del sistema."""

    def test_tipo_servicio_values(self):
        """TipoServicio tiene los valores correctos."""
        assert TipoServicio.INSTALACION == "instalacion"
        assert TipoServicio.REVISION == "revision"
        assert TipoServicio.MANTENIMIENTO == "mantenimiento"
        assert TipoServicio.REPARACION == "reparacion"
        assert TipoServicio.PRESUPUESTO == "presupuesto"
        assert TipoServicio.OTRO == "otro"
        assert len(TipoServicio) == 6

    def test_estado_evento_values(self):
        """EstadoEvento tiene los valores correctos."""
        assert EstadoEvento.PENDIENTE == "pendiente"
        assert EstadoEvento.COMPLETADO == "completado"
        assert EstadoEvento.CANCELADO == "cancelado"
        assert len(EstadoEvento) == 3

    def test_rol_values(self):
        """Rol tiene los valores correctos."""
        assert Rol.ADMIN == "admin"
        assert Rol.EDITOR == "editor"
        assert len(Rol) == 2

    def test_prioridad_values(self):
        """Prioridad tiene los valores correctos."""
        assert Prioridad.NORMAL == "normal"
        assert Prioridad.ALTA == "alta"
        assert len(Prioridad) == 2


class TestCliente:
    """Tests para el modelo Cliente."""

    def test_create_minimal_cliente(self):
        """Se puede crear un cliente con solo el nombre."""
        cliente = Cliente(nombre="Juan Pérez")
        assert cliente.nombre == "Juan Pérez"
        assert cliente.id is None
        assert cliente.telefono is None
        assert cliente.direccion is None
        assert cliente.notas is None

    def test_create_full_cliente(self):
        """Se puede crear un cliente con todos los campos."""
        cliente = Cliente(
            id=1,
            nombre="María García",
            telefono="+5491155556666",
            direccion="Av. Corrientes 1234",
            notas="Cliente VIP",
            created_at=datetime(2026, 1, 1, 10, 0),
            updated_at=datetime(2026, 1, 1, 10, 0),
        )
        assert cliente.id == 1
        assert cliente.nombre == "María García"
        assert cliente.telefono == "+5491155556666"

    def test_cliente_requires_nombre(self):
        """El nombre es obligatorio."""
        with pytest.raises(Exception):
            Cliente()

    def test_cliente_nombre_min_length(self):
        """El nombre no puede ser cadena vacía."""
        with pytest.raises(Exception):
            Cliente(nombre="")


class TestEvento:
    """Tests para el modelo Evento."""

    def test_create_minimal_evento(self):
        """Se puede crear un evento con los campos mínimos."""
        evento = Evento(
            cliente_id=1,
            tipo_servicio=TipoServicio.INSTALACION,
            fecha_hora=datetime(2026, 3, 15, 10, 0),
        )
        assert evento.cliente_id == 1
        assert evento.tipo_servicio == TipoServicio.INSTALACION
        assert evento.prioridad == Prioridad.NORMAL
        assert evento.duracion_minutos == 60
        assert evento.estado == EstadoEvento.PENDIENTE
        assert evento.id is None

    def test_evento_prioridad_alta(self):
        """Se puede crear un evento con prioridad alta."""
        evento = Evento(
            cliente_id=1,
            tipo_servicio=TipoServicio.REPARACION,
            prioridad=Prioridad.ALTA,
            fecha_hora=datetime(2026, 3, 15, 10, 0),
        )
        assert evento.prioridad == Prioridad.ALTA

    def test_evento_prioridad_from_string(self):
        """Se puede crear un evento con prioridad como string."""
        evento = Evento(
            cliente_id=1,
            tipo_servicio=TipoServicio.REPARACION,
            prioridad="alta",
            fecha_hora=datetime(2026, 3, 15, 10, 0),
        )
        assert evento.prioridad == Prioridad.ALTA

    def test_evento_duracion_constraints(self):
        """La duración tiene restricciones de min/max."""
        # 15 minutos es válido
        evento = Evento(
            cliente_id=1,
            tipo_servicio=TipoServicio.REVISION,
            fecha_hora=datetime(2026, 3, 15, 10, 0),
            duracion_minutos=15,
        )
        assert evento.duracion_minutos == 15

        # 480 minutos es válido
        evento = Evento(
            cliente_id=1,
            tipo_servicio=TipoServicio.REVISION,
            fecha_hora=datetime(2026, 3, 15, 10, 0),
            duracion_minutos=480,
        )
        assert evento.duracion_minutos == 480

        # Menos de 15 no es válido
        with pytest.raises(Exception):
            Evento(
                cliente_id=1,
                tipo_servicio=TipoServicio.REVISION,
                fecha_hora=datetime(2026, 3, 15, 10, 0),
                duracion_minutos=10,
            )

        # Más de 480 no es válido
        with pytest.raises(Exception):
            Evento(
                cliente_id=1,
                tipo_servicio=TipoServicio.REVISION,
                fecha_hora=datetime(2026, 3, 15, 10, 0),
                duracion_minutos=500,
            )

    def test_evento_emoji_property(self):
        """El emoji corresponde al tipo de servicio."""
        evento = Evento(
            cliente_id=1,
            tipo_servicio=TipoServicio.INSTALACION,
            fecha_hora=datetime(2026, 3, 15, 10, 0),
        )
        assert evento.emoji == "🔧"

        evento2 = Evento(
            cliente_id=1,
            tipo_servicio=TipoServicio.REPARACION,
            fecha_hora=datetime(2026, 3, 15, 10, 0),
        )
        assert evento2.emoji == "⚡"

    def test_evento_hora_formateada(self):
        """hora_formateada devuelve HH:MM."""
        evento = Evento(
            cliente_id=1,
            tipo_servicio=TipoServicio.REVISION,
            fecha_hora=datetime(2026, 3, 15, 14, 30),
        )
        assert evento.hora_formateada == "14:30"

    def test_evento_with_fotos(self):
        """Se pueden almacenar fotos como lista de strings."""
        evento = Evento(
            cliente_id=1,
            tipo_servicio=TipoServicio.INSTALACION,
            fecha_hora=datetime(2026, 3, 15, 10, 0),
            fotos=["foto1.jpg", "foto2.jpg"],
        )
        assert evento.fotos == ["foto1.jpg", "foto2.jpg"]

    def test_evento_tipo_servicio_from_string(self):
        """Se puede crear un evento con tipo_servicio como string."""
        evento = Evento(
            cliente_id=1,
            tipo_servicio="instalacion",
            fecha_hora=datetime(2026, 3, 15, 10, 0),
        )
        assert evento.tipo_servicio == TipoServicio.INSTALACION

    def test_evento_monto_cobrado_non_negative(self):
        """monto_cobrado no puede ser negativo."""
        with pytest.raises(Exception):
            Evento(
                cliente_id=1,
                tipo_servicio=TipoServicio.INSTALACION,
                fecha_hora=datetime(2026, 3, 15, 10, 0),
                monto_cobrado=-100.0,
            )

    def test_evento_monto_cobrado_zero_is_valid(self):
        """monto_cobrado=0 es válido (ej: garantía)."""
        evento = Evento(
            cliente_id=1,
            tipo_servicio=TipoServicio.INSTALACION,
            fecha_hora=datetime(2026, 3, 15, 10, 0),
            monto_cobrado=0.0,
        )
        assert evento.monto_cobrado == 0.0


class TestUsuarioAutorizado:
    """Tests para el modelo UsuarioAutorizado."""

    def test_create_usuario(self):
        """Se puede crear un usuario autorizado."""
        usuario = UsuarioAutorizado(
            telegram_id=123456789,
            nombre="Admin",
            rol=Rol.ADMIN,
        )
        assert usuario.telegram_id == 123456789
        assert usuario.rol == Rol.ADMIN
        assert usuario.activo is True

    def test_usuario_defaults(self):
        """Los valores por defecto son correctos."""
        usuario = UsuarioAutorizado(
            telegram_id=111,
            rol=Rol.EDITOR,
        )
        assert usuario.activo is True
        assert usuario.nombre is None
        assert usuario.id is None
