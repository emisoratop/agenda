# tests/unit/test_repository.py
"""Tests para el Repository con BD en memoria."""

import pytest
import aiosqlite
from datetime import datetime, date

from src.db.models import Cliente, Evento, Prioridad, TipoServicio, EstadoEvento
from src.db.repository import Repository
from src.core.exceptions import DuplicateClienteError, DatabaseError


# Fixtures db_connection, repo, sample_cliente, sample_evento están en conftest.py


class TestClienteCRUD:
    """Tests de CRUD de clientes."""

    async def test_create_cliente(self, repo, sample_cliente):
        """Crear un cliente devuelve su ID."""
        client_id = await repo.create_cliente(sample_cliente)
        assert client_id == 1

    async def test_get_cliente_by_id(self, repo, sample_cliente):
        """Obtener un cliente por ID."""
        client_id = await repo.create_cliente(sample_cliente)
        cliente = await repo.get_cliente_by_id(client_id)
        assert cliente is not None
        assert cliente.nombre == "Juan Pérez"
        assert cliente.telefono == "+5491155551234"

    async def test_get_cliente_by_id_not_found(self, repo):
        """Obtener un cliente inexistente devuelve None."""
        cliente = await repo.get_cliente_by_id(999)
        assert cliente is None

    async def test_get_cliente_by_telefono(self, repo, sample_cliente):
        """Obtener un cliente por teléfono."""
        await repo.create_cliente(sample_cliente)
        cliente = await repo.get_cliente_by_telefono("+5491155551234")
        assert cliente is not None
        assert cliente.nombre == "Juan Pérez"

    async def test_get_cliente_by_telefono_not_found(self, repo):
        """Buscar por teléfono inexistente devuelve None."""
        cliente = await repo.get_cliente_by_telefono("+0000000000")
        assert cliente is None

    async def test_list_clientes(self, repo):
        """Listar clientes devuelve todos ordenados por nombre."""
        await repo.create_cliente(Cliente(nombre="Zeta García"))
        await repo.create_cliente(Cliente(nombre="Ana López"))
        await repo.create_cliente(Cliente(nombre="María Rodríguez"))

        clientes = await repo.list_clientes()
        assert len(clientes) == 3
        assert clientes[0].nombre == "Ana López"
        assert clientes[1].nombre == "María Rodríguez"
        assert clientes[2].nombre == "Zeta García"

    async def test_list_clientes_empty(self, repo):
        """Listar clientes vacío devuelve lista vacía."""
        clientes = await repo.list_clientes()
        assert clientes == []

    async def test_update_cliente(self, repo, sample_cliente):
        """Actualizar campos de un cliente."""
        client_id = await repo.create_cliente(sample_cliente)
        updated = await repo.update_cliente(
            client_id, nombre="Juan P. Pérez", notas="Actualizado"
        )
        assert updated is True

        cliente = await repo.get_cliente_by_id(client_id)
        assert cliente.nombre == "Juan P. Pérez"
        assert cliente.notas == "Actualizado"

    async def test_update_cliente_not_found(self, repo):
        """Actualizar un cliente inexistente devuelve False."""
        updated = await repo.update_cliente(999, nombre="Test")
        assert updated is False

    async def test_update_cliente_no_kwargs(self, repo, sample_cliente):
        """Actualizar sin kwargs devuelve False."""
        await repo.create_cliente(sample_cliente)
        updated = await repo.update_cliente(1)
        assert updated is False

    async def test_duplicate_telefono_raises(self, repo):
        """Crear dos clientes con el mismo teléfono lanza DuplicateClienteError."""
        await repo.create_cliente(
            Cliente(nombre="Cliente 1", telefono="+5491100001111")
        )
        with pytest.raises(DuplicateClienteError):
            await repo.create_cliente(
                Cliente(nombre="Cliente 2", telefono="+5491100001111")
            )


class TestEventoCRUD:
    """Tests de CRUD de eventos."""

    async def _create_client(self, repo) -> int:
        """Helper: crea un cliente y devuelve su ID."""
        return await repo.create_cliente(Cliente(nombre="Test Client"))

    async def test_create_evento(self, repo, sample_evento):
        """Crear un evento devuelve su ID."""
        await self._create_client(repo)
        evento_id = await repo.create_evento(sample_evento)
        assert evento_id == 1

    async def test_get_evento_by_id(self, repo, sample_evento):
        """Obtener un evento por ID."""
        await self._create_client(repo)
        evento_id = await repo.create_evento(sample_evento)
        evento = await repo.get_evento_by_id(evento_id)
        assert evento is not None
        assert evento.tipo_servicio == TipoServicio.INSTALACION
        assert evento.notas == "Instalar aire acondicionado"

    async def test_get_evento_by_id_not_found(self, repo):
        """Obtener un evento inexistente devuelve None."""
        evento = await repo.get_evento_by_id(999)
        assert evento is None

    async def test_list_eventos_pendientes(self, repo):
        """Listar eventos pendientes."""
        client_id = await self._create_client(repo)
        await repo.create_evento(
            Evento(
                cliente_id=client_id,
                tipo_servicio=TipoServicio.INSTALACION,
                fecha_hora=datetime(2026, 3, 15, 10, 0),
            )
        )
        await repo.create_evento(
            Evento(
                cliente_id=client_id,
                tipo_servicio=TipoServicio.REVISION,
                fecha_hora=datetime(2026, 3, 16, 14, 0),
            )
        )

        pendientes = await repo.list_eventos_pendientes()
        assert len(pendientes) == 2
        assert pendientes[0].fecha_hora < pendientes[1].fecha_hora

    async def test_update_evento(self, repo, sample_evento):
        """Actualizar campos de un evento."""
        await self._create_client(repo)
        evento_id = await repo.create_evento(sample_evento)
        updated = await repo.update_evento(evento_id, notas="Actualizado")
        assert updated is True

        evento = await repo.get_evento_by_id(evento_id)
        assert evento.notas == "Actualizado"

    async def test_update_evento_not_found(self, repo):
        """Actualizar un evento inexistente devuelve False."""
        updated = await repo.update_evento(999, notas="Test")
        assert updated is False

    async def test_complete_evento(self, repo, sample_evento):
        """Completar un evento con datos de cierre."""
        await self._create_client(repo)
        evento_id = await repo.create_evento(sample_evento)
        completed = await repo.complete_evento(
            evento_id,
            trabajo_realizado="Instalación completa",
            monto_cobrado=15000.0,
        )
        assert completed is True

        evento = await repo.get_evento_by_id(evento_id)
        assert evento.estado == EstadoEvento.COMPLETADO
        assert evento.trabajo_realizado == "Instalación completa"
        assert evento.monto_cobrado == 15000.0

    async def test_complete_evento_without_closure_data(self, repo, sample_evento):
        """Completar un evento sin datos de cierre."""
        await self._create_client(repo)
        evento_id = await repo.create_evento(sample_evento)
        completed = await repo.complete_evento(evento_id)
        assert completed is True

        evento = await repo.get_evento_by_id(evento_id)
        assert evento.estado == EstadoEvento.COMPLETADO

    async def test_complete_evento_with_fotos_list(self, repo, sample_evento):
        """complete_evento serializa fotos list a JSON string."""
        await self._create_client(repo)
        evento_id = await repo.create_evento(sample_evento)
        fotos = ["https://example.com/foto1.jpg", "https://example.com/foto2.jpg"]
        completed = await repo.complete_evento(
            evento_id,
            trabajo_realizado="Instalación OK",
            fotos=fotos,
        )
        assert completed is True

        evento = await repo.get_evento_by_id(evento_id)
        assert evento.estado == EstadoEvento.COMPLETADO
        assert evento.fotos == fotos  # Pydantic deserializa JSON string a list

    async def test_delete_evento(self, repo, sample_evento):
        """Eliminar un evento."""
        await self._create_client(repo)
        evento_id = await repo.create_evento(sample_evento)
        deleted = await repo.delete_evento(evento_id)
        assert deleted is True

        evento = await repo.get_evento_by_id(evento_id)
        assert evento is None

    async def test_delete_evento_not_found(self, repo):
        """Eliminar un evento inexistente devuelve False."""
        deleted = await repo.delete_evento(999)
        assert deleted is False

    async def test_foreign_key_enforcement(self, repo):
        """No se puede crear un evento con cliente_id inexistente."""
        evento = Evento(
            cliente_id=999,
            tipo_servicio=TipoServicio.INSTALACION,
            fecha_hora=datetime(2026, 3, 15, 10, 0),
        )
        with pytest.raises(DatabaseError):
            await repo.create_evento(evento)

    async def test_evento_with_fotos(self, repo):
        """Crear y recuperar un evento con fotos."""
        client_id = await self._create_client(repo)
        evento = Evento(
            cliente_id=client_id,
            tipo_servicio=TipoServicio.INSTALACION,
            fecha_hora=datetime(2026, 3, 15, 10, 0),
            fotos=["foto1.jpg", "foto2.jpg"],
        )
        evento_id = await repo.create_evento(evento)
        recovered = await repo.get_evento_by_id(evento_id)
        assert recovered.fotos == ["foto1.jpg", "foto2.jpg"]

    async def test_evento_prioridad_default(self, repo):
        """Evento sin prioridad explícita se guarda como 'normal'."""
        client_id = await self._create_client(repo)
        evento = Evento(
            cliente_id=client_id,
            tipo_servicio=TipoServicio.INSTALACION,
            fecha_hora=datetime(2026, 3, 15, 10, 0),
        )
        evento_id = await repo.create_evento(evento)
        recovered = await repo.get_evento_by_id(evento_id)
        assert recovered.prioridad == Prioridad.NORMAL

    async def test_evento_prioridad_alta_roundtrip(self, repo):
        """Evento con prioridad alta se guarda y recupera correctamente."""
        client_id = await self._create_client(repo)
        evento = Evento(
            cliente_id=client_id,
            tipo_servicio=TipoServicio.REPARACION,
            prioridad=Prioridad.ALTA,
            fecha_hora=datetime(2026, 3, 15, 10, 0),
            notas="Urgente - cliente sin servicio",
        )
        evento_id = await repo.create_evento(evento)
        recovered = await repo.get_evento_by_id(evento_id)
        assert recovered.prioridad == Prioridad.ALTA

    async def test_list_eventos_by_date(self, repo):
        """Listar eventos de una fecha específica."""
        client_id = await self._create_client(repo)
        await repo.create_evento(
            Evento(
                cliente_id=client_id,
                tipo_servicio=TipoServicio.INSTALACION,
                fecha_hora=datetime(2026, 3, 15, 10, 0),
            )
        )
        await repo.create_evento(
            Evento(
                cliente_id=client_id,
                tipo_servicio=TipoServicio.REVISION,
                fecha_hora=datetime(2026, 3, 15, 14, 0),
            )
        )
        await repo.create_evento(
            Evento(
                cliente_id=client_id,
                tipo_servicio=TipoServicio.MANTENIMIENTO,
                fecha_hora=datetime(2026, 3, 16, 10, 0),
            )
        )

        eventos = await repo.list_eventos_by_date(date(2026, 3, 15))
        assert len(eventos) == 2
        assert eventos[0].tipo_servicio == TipoServicio.INSTALACION
        assert eventos[1].tipo_servicio == TipoServicio.REVISION


class TestCacheIntegration:
    """Tests de integración del caché con el Repository."""

    async def test_list_clientes_uses_cache(self, repo):
        """list_clientes usa caché en la segunda llamada."""
        await repo.create_cliente(Cliente(nombre="Test"))

        # Primera llamada: consulta a BD
        clientes1 = await repo.list_clientes()
        assert len(clientes1) == 1

        # Segunda llamada: debería venir del caché
        clientes2 = await repo.list_clientes()
        assert len(clientes2) == 1
        assert clientes1[0].nombre == clientes2[0].nombre

    async def test_create_invalidates_cache(self, repo):
        """Crear un cliente invalida el caché de clientes."""
        await repo.create_cliente(Cliente(nombre="Primero"))
        clientes = await repo.list_clientes()
        assert len(clientes) == 1

        await repo.create_cliente(Cliente(nombre="Segundo"))
        clientes = await repo.list_clientes()
        assert len(clientes) == 2

    async def test_update_invalidates_cache(self, repo):
        """Actualizar un cliente invalida el caché."""
        client_id = await repo.create_cliente(Cliente(nombre="Original"))
        _ = await repo.list_clientes()  # Llena caché

        await repo.update_cliente(client_id, nombre="Modificado")
        clientes = await repo.list_clientes()
        assert clientes[0].nombre == "Modificado"


class TestFieldWhitelists:
    """Tests de whitelists contra SQL injection vía kwargs keys."""

    async def _create_client(self, repo) -> int:
        return await repo.create_cliente(Cliente(nombre="Test Client"))

    async def test_update_cliente_rejects_invalid_field(self, repo):
        """update_cliente rechaza campos no permitidos."""
        client_id = await repo.create_cliente(Cliente(nombre="Test"))
        with pytest.raises(ValueError, match="Campos no permitidos para cliente"):
            await repo.update_cliente(client_id, id=999)

    async def test_update_cliente_rejects_sql_injection_key(self, repo):
        """update_cliente rechaza claves con SQL injection."""
        client_id = await repo.create_cliente(Cliente(nombre="Test"))
        with pytest.raises(ValueError, match="Campos no permitidos para cliente"):
            await repo.update_cliente(client_id, **{"nombre = 'hacked' --": "x"})

    async def test_update_evento_rejects_invalid_field(self, repo, sample_evento):
        """update_evento rechaza campos no permitidos."""
        await self._create_client(repo)
        evento_id = await repo.create_evento(sample_evento)
        with pytest.raises(ValueError, match="Campos no permitidos para evento"):
            await repo.update_evento(evento_id, id=999)

    async def test_complete_evento_rejects_invalid_field(self, repo, sample_evento):
        """complete_evento rechaza campos no permitidos."""
        await self._create_client(repo)
        evento_id = await repo.create_evento(sample_evento)
        with pytest.raises(ValueError, match="Campos no permitidos para cierre"):
            await repo.complete_evento(evento_id, estado="cancelado")
