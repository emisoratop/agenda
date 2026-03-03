# tests/unit/test_formatters.py
"""Tests para el módulo de formateo de respuestas del bot."""

from datetime import datetime

import pytest

from src.bot.constants import TELEGRAM_MAX_LENGTH
from src.bot.formatters import (
    format_closure_confirmation,
    format_contacts_list,
    format_event_confirmation,
    format_event_detail,
    format_events_list,
    split_message,
)
from src.db.models import (
    Cliente,
    EstadoEvento,
    Evento,
    TipoServicio,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_evento(
    id_: int = 1,
    cliente_id: int = 1,
    tipo: TipoServicio = TipoServicio.INSTALACION,
    hora: int = 10,
    dia: int = 15,
    notas: str | None = "Nota de prueba",
    estado: EstadoEvento = EstadoEvento.PENDIENTE,
    **kwargs,
) -> Evento:
    """Crea un Evento de prueba."""
    return Evento(
        id=id_,
        cliente_id=cliente_id,
        tipo_servicio=tipo,
        fecha_hora=datetime(2026, 3, dia, hora, 0),
        duracion_minutos=60,
        notas=notas,
        estado=estado,
        **kwargs,
    )


def _make_cliente(
    id_: int = 1,
    nombre: str = "Juan Pérez",
    telefono: str | None = "+5491155551234",
    direccion: str | None = "Av. Corrientes 1234",
) -> Cliente:
    """Crea un Cliente de prueba."""
    return Cliente(id=id_, nombre=nombre, telefono=telefono, direccion=direccion)


# ── format_events_list ────────────────────────────────────────────────────────


class TestFormatEventsList:
    """Tests para format_events_list()."""

    def test_empty_list(self):
        """Lista vacía retorna mensaje por defecto."""
        result = format_events_list([])
        assert "No hay eventos pendientes" in result

    def test_single_event_has_day_header(self):
        """Un evento muestra el encabezado del día."""
        evento = _make_evento(dia=15)
        result = format_events_list([evento])
        assert "15/03/2026" in result

    def test_single_event_has_hora(self):
        """Un evento muestra la hora formateada."""
        evento = _make_evento(hora=10)
        result = format_events_list([evento])
        assert "10:00" in result

    def test_event_has_emoji(self):
        """Un evento de instalación muestra el emoji correspondiente."""
        evento = _make_evento(tipo=TipoServicio.INSTALACION)
        result = format_events_list([evento])
        assert "🔵" in result

    def test_event_shows_tipo(self):
        """Muestra el tipo de servicio."""
        evento = _make_evento(tipo=TipoServicio.INSTALACION)
        result = format_events_list([evento])
        assert "Instalacion" in result

    def test_with_clientes_dict(self):
        """Usa el nombre del cliente del diccionario."""
        evento = _make_evento(cliente_id=1)
        cliente = _make_cliente(id_=1, nombre="Ana García")
        clientes = {1: cliente}
        result = format_events_list([evento], clientes)
        assert "Ana García" in result

    def test_without_clientes_dict(self):
        """Sin diccionario de clientes, muestra fallback con ID."""
        evento = _make_evento(cliente_id=5)
        result = format_events_list([evento])
        assert "Cliente #5" in result

    def test_events_grouped_by_day(self):
        """Eventos de distintos días se agrupan correctamente."""
        ev1 = _make_evento(id_=1, dia=15, hora=10)
        ev2 = _make_evento(id_=2, dia=16, hora=14)
        result = format_events_list([ev1, ev2])
        assert "15/03/2026" in result
        assert "16/03/2026" in result

    def test_day_header_has_day_name(self):
        """El encabezado incluye el nombre del día en español."""
        # 15/03/2026 es domingo
        evento = _make_evento(dia=15)
        result = format_events_list([evento])
        assert "Domingo" in result

    def test_result_is_markdown(self):
        """El resultado contiene formato Markdown (asteriscos)."""
        evento = _make_evento()
        result = format_events_list([evento])
        assert "*" in result


# ── format_event_confirmation ─────────────────────────────────────────────────


class TestFormatEventConfirmation:
    """Tests para format_event_confirmation()."""

    def test_has_tipo_servicio(self):
        """Siempre muestra el tipo de servicio."""
        data = {"tipo_servicio": "instalacion", "cliente_nombre": "Juan"}
        result = format_event_confirmation(data)
        assert "Instalacion" in result

    def test_never_shows_sin_tipo(self):
        """Nunca muestra 'Sin tipo' — usa 'otro' como fallback."""
        data = {"tipo_servicio": None, "cliente_nombre": "Juan"}
        result = format_event_confirmation(data)
        assert "Sin tipo" not in result

    def test_null_tipo_defaults_to_otro(self):
        """Si tipo_servicio es 'null', muestra 'Otro'."""
        data = {"tipo_servicio": "null", "cliente_nombre": "Juan"}
        result = format_event_confirmation(data)
        assert "Otro" in result

    def test_shows_cliente(self):
        """Muestra el nombre del cliente."""
        data = {"tipo_servicio": "revision", "cliente_nombre": "Ana García"}
        result = format_event_confirmation(data)
        assert "Ana García" in result

    def test_shows_confirmation_question(self):
        """Incluye la pregunta de confirmación."""
        data = {"tipo_servicio": "otro"}
        result = format_event_confirmation(data)
        assert "Confirmás" in result

    def test_has_summary_header(self):
        """Tiene el encabezado de resumen."""
        data = {"tipo_servicio": "otro"}
        result = format_event_confirmation(data)
        assert "Resumen" in result

    def test_shows_telefono(self):
        """Muestra teléfono si está disponible."""
        data = {"tipo_servicio": "otro", "telefono": "+5491155551234"}
        result = format_event_confirmation(data)
        assert "+5491155551234" in result

    def test_shows_direccion(self):
        """Muestra dirección si está disponible."""
        data = {"tipo_servicio": "otro", "direccion": "Av. Corrientes 1234"}
        result = format_event_confirmation(data)
        assert "Av. Corrientes 1234" in result

    def test_structured_dict_from_orchestrator(self):
        """Soporta el dict estructurado {evento, cliente, parsed} del orchestrator."""
        evento = _make_evento(tipo=TipoServicio.INSTALACION, dia=3, hora=15)
        cliente = _make_cliente(
            nombre="Juan Pérez",
            telefono="2604264937",
            direccion="Balcarce 1783",
        )
        data = {"evento": evento, "cliente": cliente, "parsed": None}
        result = format_event_confirmation(data)
        assert "Instalacion" in result
        assert "Juan Pérez" in result
        assert "2604264937" in result
        assert "Balcarce 1783" in result
        assert "03/03/2026" in result
        assert "15:00" in result

    def test_structured_dict_with_parsed_direccion(self):
        """Si el cliente no tiene dirección, la toma del parsed."""
        from src.llm.schemas import ParsedEvent

        evento = _make_evento(tipo=TipoServicio.REVISION, dia=5, hora=10)
        cliente = _make_cliente(nombre="Ana", telefono=None, direccion=None)
        parsed = ParsedEvent(
            cliente_nombre="Ana",
            cliente_telefono="351999888",
            direccion="San Martín 456",
        )
        data = {"evento": evento, "cliente": cliente, "parsed": parsed}
        result = format_event_confirmation(data)
        assert "San Martín 456" in result
        assert "351999888" in result

    def test_phone_match_warning_when_names_differ(self):
        """Muestra advertencia cuando el cliente resuelto difiere del parseado."""
        from src.llm.schemas import ParsedEvent

        evento = _make_evento(tipo=TipoServicio.INSTALACION, dia=10, hora=9)
        # El teléfono pertenece a Juan Pérez en la DB
        cliente = _make_cliente(
            nombre="Juan Pérez", telefono="2604264937", direccion="Calle 1"
        )
        # Pero el usuario dijo "Emiliano Sorato"
        parsed = ParsedEvent(
            cliente_nombre="Emiliano Sorato",
            cliente_telefono="2604264937",
        )
        data = {"evento": evento, "cliente": cliente, "parsed": parsed}
        result = format_event_confirmation(data)
        assert "⚠️" in result
        assert "Juan Pérez" in result
        assert "Emiliano Sorato" in result
        assert "teléfono ya pertenece" in result

    def test_no_warning_when_names_match(self):
        """No muestra advertencia cuando los nombres coinciden."""
        from src.llm.schemas import ParsedEvent

        evento = _make_evento(tipo=TipoServicio.INSTALACION, dia=10, hora=9)
        cliente = _make_cliente(
            nombre="Juan Pérez", telefono="2604264937", direccion="Calle 1"
        )
        parsed = ParsedEvent(
            cliente_nombre="Juan Pérez",
            cliente_telefono="2604264937",
        )
        data = {"evento": evento, "cliente": cliente, "parsed": parsed}
        result = format_event_confirmation(data)
        assert "⚠️" not in result
        assert "teléfono ya pertenece" not in result

    def test_no_warning_when_names_match_case_insensitive(self):
        """No muestra advertencia cuando los nombres coinciden (case-insensitive)."""
        from src.llm.schemas import ParsedEvent

        evento = _make_evento(tipo=TipoServicio.REVISION, dia=10, hora=9)
        cliente = _make_cliente(nombre="Ana García", telefono="351111222")
        parsed = ParsedEvent(
            cliente_nombre="ana garcía",
            cliente_telefono="351111222",
        )
        data = {"evento": evento, "cliente": cliente, "parsed": parsed}
        result = format_event_confirmation(data)
        assert "⚠️" not in result

    def test_no_warning_when_no_parsed(self):
        """No muestra advertencia cuando parsed es None."""
        evento = _make_evento(tipo=TipoServicio.INSTALACION, dia=10, hora=9)
        cliente = _make_cliente(nombre="Juan Pérez", telefono="2604264937")
        data = {"evento": evento, "cliente": cliente, "parsed": None}
        result = format_event_confirmation(data)
        assert "⚠️" not in result


# ── format_event_detail ───────────────────────────────────────────────────────


class TestFormatEventDetail:
    """Tests para format_event_detail()."""

    def test_shows_event_id(self):
        """Muestra el ID del evento."""
        evento = _make_evento(id_=42)
        result = format_event_detail(evento)
        assert "42" in result

    def test_shows_tipo_servicio(self):
        """Muestra el tipo de servicio."""
        evento = _make_evento(tipo=TipoServicio.REPARACION)
        result = format_event_detail(evento)
        assert "Reparacion" in result

    def test_shows_emoji(self):
        """Muestra el emoji del tipo de servicio."""
        evento = _make_evento(tipo=TipoServicio.INSTALACION)
        result = format_event_detail(evento)
        assert "🔵" in result

    def test_shows_fecha(self):
        """Muestra la fecha formateada."""
        evento = _make_evento(dia=15)
        result = format_event_detail(evento)
        assert "15/03/2026" in result

    def test_shows_hora(self):
        """Muestra la hora formateada."""
        evento = _make_evento(hora=15)
        result = format_event_detail(evento)
        assert "15:00" in result

    def test_shows_duracion(self):
        """Muestra la duración en minutos."""
        evento = _make_evento()
        result = format_event_detail(evento)
        assert "60 min" in result

    def test_shows_estado(self):
        """Muestra el estado del evento."""
        evento = _make_evento(estado=EstadoEvento.PENDIENTE)
        result = format_event_detail(evento)
        assert "Pendiente" in result

    def test_shows_notas(self):
        """Muestra las notas si existen."""
        evento = _make_evento(notas="Nota importante")
        result = format_event_detail(evento)
        assert "Nota importante" in result

    def test_no_notas_omits_field(self):
        """Si no hay notas, no muestra el campo."""
        evento = _make_evento(notas=None)
        result = format_event_detail(evento)
        assert "Notas:" not in result

    def test_with_cliente_shows_name(self):
        """Con cliente, muestra su nombre."""
        evento = _make_evento(cliente_id=1)
        cliente = _make_cliente(nombre="Ana García")
        result = format_event_detail(evento, cliente)
        assert "Ana García" in result

    def test_without_cliente_shows_fallback(self):
        """Sin cliente, muestra fallback con ID."""
        evento = _make_evento(cliente_id=5)
        result = format_event_detail(evento)
        assert "Cliente #5" in result

    def test_with_cliente_telefono(self):
        """Con cliente con teléfono, muestra el teléfono."""
        evento = _make_evento()
        cliente = _make_cliente(telefono="+5491155551234")
        result = format_event_detail(evento, cliente)
        assert "+5491155551234" in result

    def test_with_cliente_direccion(self):
        """Con cliente con dirección, muestra la dirección."""
        evento = _make_evento()
        cliente = _make_cliente(direccion="Balcarce 132")
        result = format_event_detail(evento, cliente)
        assert "Balcarce 132" in result


# ── format_contacts_list ──────────────────────────────────────────────────────


class TestFormatContactsList:
    """Tests para format_contacts_list()."""

    def test_empty_list(self):
        """Lista vacía retorna mensaje por defecto."""
        result = format_contacts_list([])
        assert "No hay contactos" in result

    def test_single_contact_shows_name(self):
        """Un contacto muestra su nombre."""
        cliente = _make_cliente(nombre="Juan Pérez")
        result = format_contacts_list([cliente])
        assert "Juan Pérez" in result

    def test_shows_telefono(self):
        """Muestra el teléfono del contacto."""
        cliente = _make_cliente(telefono="+5491155551234")
        result = format_contacts_list([cliente])
        assert "+5491155551234" in result

    def test_no_telefono_shows_sin_telefono(self):
        """Sin teléfono muestra 'Sin teléfono'."""
        cliente = _make_cliente(telefono=None)
        result = format_contacts_list([cliente])
        assert "Sin teléfono" in result

    def test_shows_direccion(self):
        """Muestra la dirección si existe."""
        cliente = _make_cliente(direccion="Av. Corrientes 1234")
        result = format_contacts_list([cliente])
        assert "Av. Corrientes 1234" in result

    def test_no_direccion_omits(self):
        """Sin dirección, no muestra el campo."""
        cliente = _make_cliente(direccion=None)
        result = format_contacts_list([cliente])
        assert "📍" not in result

    def test_multiple_contacts(self):
        """Múltiples contactos se formatean correctamente."""
        c1 = _make_cliente(id_=1, nombre="Juan")
        c2 = _make_cliente(id_=2, nombre="Ana")
        result = format_contacts_list([c1, c2])
        assert "Juan" in result
        assert "Ana" in result

    def test_result_is_markdown(self):
        """El resultado usa formato Markdown."""
        cliente = _make_cliente()
        result = format_contacts_list([cliente])
        assert "*" in result


# ── format_closure_confirmation ───────────────────────────────────────────────


class TestFormatClosureConfirmation:
    """Tests para format_closure_confirmation()."""

    def test_shows_cierre_header(self):
        """Muestra el encabezado de cierre."""
        evento = _make_evento()
        result = format_closure_confirmation(evento)
        assert "Cierre de servicio" in result

    def test_shows_tipo_servicio(self):
        """Muestra el tipo de servicio."""
        evento = _make_evento(tipo=TipoServicio.INSTALACION)
        result = format_closure_confirmation(evento)
        assert "Instalacion" in result

    def test_shows_emoji(self):
        """Muestra el emoji del servicio."""
        evento = _make_evento(tipo=TipoServicio.INSTALACION)
        result = format_closure_confirmation(evento)
        assert "🔵" in result

    def test_with_cliente_name(self):
        """Con cliente, muestra su nombre."""
        evento = _make_evento()
        cliente = _make_cliente(nombre="María López")
        result = format_closure_confirmation(evento, cliente)
        assert "María López" in result

    def test_without_cliente_shows_fallback(self):
        """Sin cliente, muestra fallback con ID."""
        evento = _make_evento(cliente_id=5)
        result = format_closure_confirmation(evento)
        assert "Cliente #5" in result

    def test_shows_trabajo_realizado(self):
        """Muestra el trabajo realizado si existe."""
        evento = _make_evento(trabajo_realizado="Instalé 4 cámaras")
        result = format_closure_confirmation(evento)
        assert "Instalé 4 cámaras" in result

    def test_shows_monto_cobrado(self):
        """Muestra el monto cobrado si existe."""
        evento = _make_evento(monto_cobrado=150000.0)
        result = format_closure_confirmation(evento)
        assert "$150,000" in result

    def test_shows_notas_cierre(self):
        """Muestra las notas de cierre si existen."""
        evento = _make_evento(notas_cierre="Todo ok")
        result = format_closure_confirmation(evento)
        assert "Todo ok" in result

    def test_shows_fotos_count(self):
        """Muestra la cantidad de fotos si existen."""
        evento = _make_evento(fotos=["foto1.jpg", "foto2.jpg"])
        result = format_closure_confirmation(evento)
        assert "2" in result

    def test_no_optional_fields(self):
        """Sin campos opcionales, muestra solo lo básico."""
        evento = _make_evento()
        result = format_closure_confirmation(evento)
        # No debería tener líneas de trabajo, monto, notas_cierre, fotos
        assert "Trabajo realizado" not in result
        assert "Monto cobrado" not in result


# ── split_message ─────────────────────────────────────────────────────────────


class TestSplitMessage:
    """Tests para split_message()."""

    def test_short_message_returns_single(self):
        """Mensaje corto retorna una sola parte."""
        result = split_message("Hola mundo")
        assert result == ["Hola mundo"]

    def test_exact_limit_returns_single(self):
        """Mensaje exactamente en el límite retorna una sola parte."""
        text = "a" * TELEGRAM_MAX_LENGTH
        result = split_message(text)
        assert len(result) == 1

    def test_long_message_splits(self):
        """Mensaje largo se divide en múltiples partes."""
        text = "\n".join(f"Línea {i}" for i in range(1000))
        result = split_message(text, max_length=100)
        assert len(result) > 1

    def test_all_parts_within_limit(self):
        """Todas las partes respetan el límite de longitud."""
        text = "\n".join(f"Línea larga número {i} con texto" for i in range(500))
        result = split_message(text, max_length=100)
        for part in result:
            assert len(part) <= 100

    def test_splits_at_newlines(self):
        """Divide en saltos de línea para no romper formato."""
        text = "Línea 1\nLínea 2\nLínea 3"
        result = split_message(text, max_length=15)
        # Debería cortar en \n, no en medio de "Línea"
        for part in result:
            assert not part.startswith("\n")

    def test_empty_message(self):
        """Mensaje vacío retorna lista con string vacío."""
        result = split_message("")
        assert result == [""]

    def test_preserves_all_content(self):
        """Todo el contenido original se preserva en las partes."""
        lines = [f"Línea {i}" for i in range(50)]
        text = "\n".join(lines)
        parts = split_message(text, max_length=100)
        combined = "\n".join(parts)
        for line in lines:
            assert line in combined
