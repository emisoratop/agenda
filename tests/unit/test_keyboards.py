# tests/unit/test_keyboards.py
"""Tests para el módulo de generación de keyboards del bot."""

from datetime import time

import pytest

from src.bot.constants import CallbackData, ITEMS_PER_PAGE
from src.bot.keyboards import (
    build_confirmation_keyboard,
    build_contact_list_keyboard,
    build_event_list_keyboard,
    build_field_selection_keyboard,
    build_main_menu,
    build_pagination_keyboard,
    build_photos_keyboard,
    build_time_slots_keyboard,
    paginate_items,
    validate_consecutive_slots,
)
from src.core.result import AvailableSlot
from src.db.models import Cliente, Evento, TipoServicio

from datetime import datetime


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_evento(id_: int = 1, hora: int = 10) -> Evento:
    """Crea un Evento de prueba."""
    return Evento(
        id=id_,
        cliente_id=1,
        tipo_servicio=TipoServicio.INSTALACION,
        fecha_hora=datetime(2026, 3, 15, hora, 0),
        duracion_minutos=60,
    )


def _make_cliente(
    id_: int = 1,
    nombre: str = "Juan Pérez",
    telefono: str | None = "+5491155551234",
    direccion: str | None = None,
) -> Cliente:
    """Crea un Cliente de prueba."""
    return Cliente(id=id_, nombre=nombre, telefono=telefono, direccion=direccion)


# ── build_main_menu ───────────────────────────────────────────────────────────


class TestBuildMainMenu:
    """Tests para build_main_menu() según el rol."""

    def test_admin_sees_all_buttons(self):
        """Admin ve todos los botones del menú."""
        keyboard = build_main_menu("admin")
        callback_datas = [
            btn.callback_data for row in keyboard.inline_keyboard for btn in row
        ]
        assert CallbackData.CREAR_EVENTO in callback_datas
        assert CallbackData.EDITAR_EVENTO in callback_datas
        assert CallbackData.VER_EVENTOS in callback_datas
        assert CallbackData.ELIMINAR_EVENTO in callback_datas
        assert CallbackData.TERMINAR_EVENTO in callback_datas
        assert CallbackData.VER_CONTACTOS in callback_datas
        assert CallbackData.EDITAR_CONTACTO in callback_datas

    def test_editor_sees_subset(self):
        """Editor ve solo los botones permitidos (no Crear, Eliminar, Editar contacto)."""
        keyboard = build_main_menu("editor")
        callback_datas = [
            btn.callback_data for row in keyboard.inline_keyboard for btn in row
        ]
        assert CallbackData.CREAR_EVENTO not in callback_datas
        assert CallbackData.ELIMINAR_EVENTO not in callback_datas
        assert CallbackData.EDITAR_CONTACTO not in callback_datas

    def test_editor_sees_common_buttons(self):
        """Editor ve botones comunes: editar, ver eventos, terminar, ver contactos."""
        keyboard = build_main_menu("editor")
        callback_datas = [
            btn.callback_data for row in keyboard.inline_keyboard for btn in row
        ]
        assert CallbackData.EDITAR_EVENTO in callback_datas
        assert CallbackData.VER_EVENTOS in callback_datas
        assert CallbackData.TERMINAR_EVENTO in callback_datas
        assert CallbackData.VER_CONTACTOS in callback_datas

    def test_admin_has_more_buttons_than_editor(self):
        """Admin tiene más botones que editor."""
        admin_kb = build_main_menu("admin")
        editor_kb = build_main_menu("editor")
        admin_count = sum(len(row) for row in admin_kb.inline_keyboard)
        editor_count = sum(len(row) for row in editor_kb.inline_keyboard)
        assert admin_count > editor_count

    def test_returns_inline_keyboard_markup(self):
        """Retorna un InlineKeyboardMarkup."""
        from telegram import InlineKeyboardMarkup

        keyboard = build_main_menu("admin")
        assert isinstance(keyboard, InlineKeyboardMarkup)


# ── build_event_list_keyboard ─────────────────────────────────────────────────


class TestBuildEventListKeyboard:
    """Tests para build_event_list_keyboard()."""

    def test_empty_list_has_cancel_button(self):
        """Lista vacía solo tiene botón Cancelar."""
        keyboard = build_event_list_keyboard([], action="editar")
        assert len(keyboard.inline_keyboard) == 1
        assert keyboard.inline_keyboard[0][0].callback_data == CallbackData.CANCEL

    def test_events_create_buttons(self):
        """Cada evento genera un botón."""
        eventos = [_make_evento(id_=1, hora=10), _make_evento(id_=2, hora=14)]
        keyboard = build_event_list_keyboard(eventos, action="editar")
        # 2 eventos + 1 cancelar
        assert len(keyboard.inline_keyboard) == 3

    def test_callback_data_uses_action_prefix(self):
        """callback_data usa el prefijo de acción + id del evento."""
        evento = _make_evento(id_=5)
        keyboard = build_event_list_keyboard([evento], action="eliminar")
        btn = keyboard.inline_keyboard[0][0]
        assert btn.callback_data == "eliminar_5"

    def test_button_label_includes_hora(self):
        """El label del botón incluye la hora formateada."""
        evento = _make_evento(id_=1, hora=15)
        keyboard = build_event_list_keyboard([evento], action="editar")
        btn = keyboard.inline_keyboard[0][0]
        assert "15:00" in btn.text

    def test_button_label_includes_emoji(self):
        """El label del botón incluye el emoji del tipo de servicio."""
        evento = _make_evento(id_=1)
        keyboard = build_event_list_keyboard([evento], action="editar")
        btn = keyboard.inline_keyboard[0][0]
        assert "🔵" in btn.text

    def test_with_clientes_shows_nombre_and_direccion(self):
        """Con dict de clientes, el label muestra fecha, hora, nombre y dirección."""
        evento = _make_evento(id_=1, hora=16)
        cliente = _make_cliente(id_=1, nombre="Ana García", direccion="Balcarce 1783")
        clientes = {1: cliente}
        keyboard = build_event_list_keyboard(
            [evento],
            action="editar",
            clientes=clientes,
        )
        btn = keyboard.inline_keyboard[0][0]
        assert "15/03" in btn.text  # fecha dd/mm
        assert "16:00" in btn.text
        assert "Ana García" in btn.text
        assert "Balcarce 1783" in btn.text

    def test_with_clientes_no_direccion(self):
        """Con dict de clientes sin dirección, el label omite la dirección."""
        evento = _make_evento(id_=1, hora=10)
        cliente = _make_cliente(id_=1, nombre="Pedro López", direccion=None)
        clientes = {1: cliente}
        keyboard = build_event_list_keyboard(
            [evento],
            action="terminar",
            clientes=clientes,
        )
        btn = keyboard.inline_keyboard[0][0]
        assert "Pedro López" in btn.text
        assert "," not in btn.text  # sin coma porque no hay dirección

    def test_without_clientes_shows_fallback(self):
        """Sin dict de clientes, el label usa el formato fallback 'Evento #N'."""
        evento = _make_evento(id_=5, hora=14)
        keyboard = build_event_list_keyboard([evento], action="eliminar")
        btn = keyboard.inline_keyboard[0][0]
        assert "Evento #5" in btn.text

    def test_label_truncated_at_64_chars(self):
        """Labels que exceden 64 caracteres se truncan con '…'."""
        evento = _make_evento(id_=1, hora=10)
        nombre_largo = "María Fernanda González de los Santos"
        direccion_larga = "Av. Libertador General San Martín 12345, Piso 8 Depto B"
        cliente = _make_cliente(
            id_=1,
            nombre=nombre_largo,
            direccion=direccion_larga,
        )
        clientes = {1: cliente}
        keyboard = build_event_list_keyboard(
            [evento],
            action="editar",
            clientes=clientes,
        )
        btn = keyboard.inline_keyboard[0][0]
        assert len(btn.text) <= 64
        assert btn.text.endswith("…")

    def test_clientes_missing_cliente_id_uses_fallback(self):
        """Si el cliente_id del evento no está en el dict, usa fallback."""
        evento = _make_evento(id_=3, hora=9)  # cliente_id=1
        clientes = {99: _make_cliente(id_=99, nombre="Otro")}
        keyboard = build_event_list_keyboard(
            [evento],
            action="editar",
            clientes=clientes,
        )
        btn = keyboard.inline_keyboard[0][0]
        assert "Evento #3" in btn.text


# ── build_contact_list_keyboard ───────────────────────────────────────────────


class TestBuildContactListKeyboard:
    """Tests para build_contact_list_keyboard()."""

    def test_empty_list_has_cancel(self):
        """Lista vacía solo tiene botón Cancelar."""
        keyboard = build_contact_list_keyboard([])
        assert len(keyboard.inline_keyboard) == 1

    def test_contacts_create_buttons(self):
        """Cada contacto genera un botón."""
        contactos = [_make_cliente(id_=1), _make_cliente(id_=2, nombre="Ana")]
        keyboard = build_contact_list_keyboard(contactos)
        # 2 contactos + 1 cancelar
        assert len(keyboard.inline_keyboard) == 3

    def test_callback_data_uses_contact_prefix(self):
        """callback_data usa el prefijo de contacto + id."""
        cliente = _make_cliente(id_=7)
        keyboard = build_contact_list_keyboard([cliente])
        btn = keyboard.inline_keyboard[0][0]
        assert btn.callback_data == f"{CallbackData.CONTACT_PREFIX}7"

    def test_button_includes_nombre(self):
        """El botón incluye el nombre del contacto."""
        cliente = _make_cliente(nombre="María López")
        keyboard = build_contact_list_keyboard([cliente])
        btn = keyboard.inline_keyboard[0][0]
        assert "María López" in btn.text

    def test_button_includes_telefono(self):
        """El botón incluye el teléfono si está disponible."""
        cliente = _make_cliente(telefono="+5491155551234")
        keyboard = build_contact_list_keyboard([cliente])
        btn = keyboard.inline_keyboard[0][0]
        assert "+5491155551234" in btn.text

    def test_button_without_telefono(self):
        """Si no tiene teléfono, no muestra guión ni teléfono."""
        cliente = _make_cliente(telefono=None)
        keyboard = build_contact_list_keyboard([cliente])
        btn = keyboard.inline_keyboard[0][0]
        assert "—" not in btn.text


# ── build_confirmation_keyboard ───────────────────────────────────────────────


class TestBuildConfirmationKeyboard:
    """Tests para build_confirmation_keyboard()."""

    def test_has_two_buttons(self):
        """Tiene exactamente 2 botones en una fila."""
        keyboard = build_confirmation_keyboard()
        assert len(keyboard.inline_keyboard) == 1
        assert len(keyboard.inline_keyboard[0]) == 2

    def test_confirm_yes_button(self):
        """Primer botón es Confirmar."""
        keyboard = build_confirmation_keyboard()
        btn = keyboard.inline_keyboard[0][0]
        assert btn.callback_data == CallbackData.CONFIRM_YES
        assert "Confirmar" in btn.text

    def test_confirm_no_button(self):
        """Segundo botón es Cancelar."""
        keyboard = build_confirmation_keyboard()
        btn = keyboard.inline_keyboard[0][1]
        assert btn.callback_data == CallbackData.CONFIRM_NO
        assert "Cancelar" in btn.text


# ── build_field_selection_keyboard ────────────────────────────────────────────


class TestBuildFieldSelectionKeyboard:
    """Tests para build_field_selection_keyboard()."""

    def test_has_five_rows(self):
        """Tiene 5 filas: 4 campos + cancelar."""
        keyboard = build_field_selection_keyboard()
        assert len(keyboard.inline_keyboard) == 5

    def test_field_callbacks(self):
        """Los callbacks de campos están correctos."""
        keyboard = build_field_selection_keyboard()
        callbacks = [row[0].callback_data for row in keyboard.inline_keyboard]
        assert CallbackData.FIELD_NOMBRE in callbacks
        assert CallbackData.FIELD_TELEFONO in callbacks
        assert CallbackData.FIELD_DIRECCION in callbacks
        assert CallbackData.FIELD_NOTAS in callbacks

    def test_last_button_is_cancel(self):
        """El último botón es Cancelar."""
        keyboard = build_field_selection_keyboard()
        last_btn = keyboard.inline_keyboard[-1][0]
        assert last_btn.callback_data == CallbackData.CANCEL


# ── build_time_slots_keyboard ─────────────────────────────────────────────────


class TestBuildTimeSlotsKeyboard:
    """Tests para build_time_slots_keyboard()."""

    def test_empty_slots(self):
        """Sin slots, solo tiene botón Cancelar."""
        keyboard = build_time_slots_keyboard([])
        assert len(keyboard.inline_keyboard) == 1
        assert keyboard.inline_keyboard[0][0].callback_data == CallbackData.CANCEL

    def test_slots_create_buttons(self):
        """Cada slot genera un botón."""
        slots = [
            AvailableSlot(start=time(10, 0), end=time(11, 0)),
            AvailableSlot(start=time(11, 0), end=time(12, 0)),
        ]
        keyboard = build_time_slots_keyboard(slots)
        # 2 slots + 1 cancelar (sin confirmar porque no hay selected)
        assert len(keyboard.inline_keyboard) == 3

    def test_slot_button_label_has_times(self):
        """El label del botón muestra las horas."""
        slot = AvailableSlot(start=time(15, 0), end=time(16, 0))
        keyboard = build_time_slots_keyboard([slot])
        btn = keyboard.inline_keyboard[0][0]
        assert "15:00" in btn.text
        assert "16:00" in btn.text

    def test_selected_slots_show_checkmark(self):
        """Los slots seleccionados muestran checkmark."""
        slots = [
            AvailableSlot(start=time(10, 0), end=time(11, 0)),
            AvailableSlot(start=time(11, 0), end=time(12, 0)),
        ]
        keyboard = build_time_slots_keyboard(slots, selected=["10:00-11:00"])
        btn_selected = keyboard.inline_keyboard[0][0]
        btn_not = keyboard.inline_keyboard[1][0]
        assert "✅" in btn_selected.text
        assert "✅" not in btn_not.text

    def test_selected_slots_show_confirm_button(self):
        """Cuando hay slots seleccionados, aparece botón de Confirmar."""
        slots = [AvailableSlot(start=time(10, 0), end=time(11, 0))]
        keyboard = build_time_slots_keyboard(slots, selected=["10:00-11:00"])
        callbacks = [
            btn.callback_data for row in keyboard.inline_keyboard for btn in row
        ]
        assert CallbackData.SLOT_CONFIRM in callbacks

    def test_no_selected_no_confirm_button(self):
        """Sin slots seleccionados, no hay botón de Confirmar."""
        slots = [AvailableSlot(start=time(10, 0), end=time(11, 0))]
        keyboard = build_time_slots_keyboard(slots)
        callbacks = [
            btn.callback_data for row in keyboard.inline_keyboard for btn in row
        ]
        assert CallbackData.SLOT_CONFIRM not in callbacks

    def test_slot_callback_data_has_prefix(self):
        """El callback_data del slot tiene el prefijo correcto."""
        slot = AvailableSlot(start=time(10, 0), end=time(11, 0))
        keyboard = build_time_slots_keyboard([slot])
        btn = keyboard.inline_keyboard[0][0]
        assert btn.callback_data.startswith(CallbackData.SLOT_PREFIX)


# ── build_photos_keyboard ────────────────────────────────────────────────────


class TestBuildPhotosKeyboard:
    """Tests para build_photos_keyboard()."""

    def test_has_two_rows(self):
        """Tiene 2 filas: listo y omitir."""
        keyboard = build_photos_keyboard()
        assert len(keyboard.inline_keyboard) == 2

    def test_done_button(self):
        """Primer botón es Listo/Continuar."""
        keyboard = build_photos_keyboard()
        btn = keyboard.inline_keyboard[0][0]
        assert btn.callback_data == CallbackData.PHOTOS_DONE

    def test_skip_button(self):
        """Segundo botón es Omitir."""
        keyboard = build_photos_keyboard()
        btn = keyboard.inline_keyboard[1][0]
        assert btn.callback_data == CallbackData.PHOTOS_SKIP


# ── validate_consecutive_slots ────────────────────────────────────────────────


class TestValidateConsecutiveSlots:
    """Tests para validate_consecutive_slots()."""

    def test_empty_list(self):
        """Lista vacía es válida."""
        assert validate_consecutive_slots([]) is True

    def test_single_slot(self):
        """Un solo slot es válido."""
        assert validate_consecutive_slots(["10:00-11:00"]) is True

    def test_two_consecutive(self):
        """Dos slots consecutivos son válidos."""
        assert validate_consecutive_slots(["10:00-11:00", "11:00-12:00"]) is True

    def test_three_consecutive(self):
        """Tres slots consecutivos son válidos."""
        result = validate_consecutive_slots(
            ["10:00-11:00", "11:00-12:00", "12:00-13:00"]
        )
        assert result is True

    def test_non_consecutive(self):
        """Slots no consecutivos son inválidos."""
        assert validate_consecutive_slots(["10:00-11:00", "14:00-15:00"]) is False

    def test_gap_between(self):
        """Slots con hueco entre medio son inválidos."""
        result = validate_consecutive_slots(
            ["10:00-11:00", "11:00-12:00", "13:00-14:00"]
        )
        assert result is False


# ── paginate_items ────────────────────────────────────────────────────────────


class TestPaginateItems:
    """Tests para paginate_items()."""

    def test_empty_list(self):
        """Lista vacía retorna lista vacía y 1 página."""
        items, total = paginate_items([], 0)
        assert items == []
        assert total == 1

    def test_single_page(self):
        """Si hay menos items que per_page, retorna todos en 1 página."""
        items, total = paginate_items([1, 2, 3], 0, per_page=5)
        assert items == [1, 2, 3]
        assert total == 1

    def test_multiple_pages(self):
        """Items se dividen correctamente en páginas."""
        items_list = list(range(12))
        page_0, total = paginate_items(items_list, 0, per_page=5)
        assert page_0 == [0, 1, 2, 3, 4]
        assert total == 3

    def test_second_page(self):
        """Segunda página retorna los items correctos."""
        items_list = list(range(12))
        page_1, total = paginate_items(items_list, 1, per_page=5)
        assert page_1 == [5, 6, 7, 8, 9]
        assert total == 3

    def test_last_page(self):
        """Última página retorna los items restantes."""
        items_list = list(range(12))
        page_2, total = paginate_items(items_list, 2, per_page=5)
        assert page_2 == [10, 11]
        assert total == 3

    def test_page_out_of_range_clamps(self):
        """Una página fuera de rango se ajusta a la última página válida."""
        items_list = list(range(5))
        page, total = paginate_items(items_list, 99, per_page=5)
        assert page == [0, 1, 2, 3, 4]
        assert total == 1

    def test_negative_page_clamps(self):
        """Una página negativa se ajusta a la primera."""
        items_list = list(range(10))
        page, total = paginate_items(items_list, -1, per_page=5)
        assert page == [0, 1, 2, 3, 4]
        assert total == 2


# ── build_pagination_keyboard ─────────────────────────────────────────────────


class TestBuildPaginationKeyboard:
    """Tests para build_pagination_keyboard()."""

    def test_single_page_returns_none(self):
        """Con una sola página retorna None."""
        result = build_pagination_keyboard(0, 1, "ev_page")
        assert result is None

    def test_first_page_has_next_only(self):
        """Primera página solo tiene botón Siguiente."""
        keyboard = build_pagination_keyboard(0, 3, "ev_page")
        labels = [btn.text for btn in keyboard.inline_keyboard[0]]
        assert "◀ Anterior" not in labels
        assert "Siguiente ▶" in labels

    def test_middle_page_has_both(self):
        """Página del medio tiene Anterior y Siguiente."""
        keyboard = build_pagination_keyboard(1, 3, "ev_page")
        labels = [btn.text for btn in keyboard.inline_keyboard[0]]
        assert "◀ Anterior" in labels
        assert "Siguiente ▶" in labels

    def test_last_page_has_prev_only(self):
        """Última página solo tiene botón Anterior."""
        keyboard = build_pagination_keyboard(2, 3, "ev_page")
        labels = [btn.text for btn in keyboard.inline_keyboard[0]]
        assert "◀ Anterior" in labels
        assert "Siguiente ▶" not in labels

    def test_page_indicator(self):
        """Muestra indicador de página actual."""
        keyboard = build_pagination_keyboard(1, 3, "ev_page")
        labels = [btn.text for btn in keyboard.inline_keyboard[0]]
        assert "2/3" in labels

    def test_callback_data_format(self):
        """callback_data usa el formato prefijo:número."""
        keyboard = build_pagination_keyboard(0, 3, "ev_page")
        next_btn = [
            btn for btn in keyboard.inline_keyboard[0] if "Siguiente" in btn.text
        ][0]
        assert next_btn.callback_data == "ev_page:1"

    def test_prev_callback_data(self):
        """Botón Anterior apunta a la página previa."""
        keyboard = build_pagination_keyboard(2, 3, "ev_page")
        prev_btn = [
            btn for btn in keyboard.inline_keyboard[0] if "Anterior" in btn.text
        ][0]
        assert prev_btn.callback_data == "ev_page:1"
