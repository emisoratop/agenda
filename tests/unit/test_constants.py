# tests/unit/test_constants.py
"""Tests para el módulo de constantes del bot."""

import pytest

from src.bot.constants import (
    ITEMS_PER_PAGE,
    SERVICE_EMOJIS,
    TELEGRAM_MAX_LENGTH,
    CallbackData,
    Messages,
    States,
    get_service_emoji,
)
from src.db.models import TipoServicio


# ── States ────────────────────────────────────────────────────────────────────


class TestStates:
    """Tests para la clase States con estados de ConversationHandler."""

    def test_crear_states_are_sequential(self):
        """Los estados de crear evento son secuenciales y no se solapan."""
        crear_states = [
            States.CREAR_DESCRIPTION,
            States.CREAR_DATE,
            States.CREAR_TIME_SLOT,
            States.CREAR_CONFIRMATION,
        ]
        assert crear_states == [0, 1, 2, 3]

    def test_editar_states_start_at_10(self):
        """Los estados de editar evento empiezan en 10."""
        assert States.EDITAR_SELECT == 10
        assert States.EDITAR_CHANGES == 11
        assert States.EDITAR_CONFIRMATION == 12

    def test_eliminar_states_start_at_20(self):
        """Los estados de eliminar evento empiezan en 20."""
        assert States.ELIMINAR_SELECT == 20
        assert States.ELIMINAR_CONFIRMATION == 21

    def test_terminar_states_start_at_30(self):
        """Los estados de terminar evento empiezan en 30."""
        assert States.TERMINAR_SELECT == 30
        assert States.TERMINAR_CLOSURE == 31
        assert States.TERMINAR_PHOTOS == 32
        assert States.TERMINAR_CONFIRMATION == 33

    def test_contacto_states_start_at_40(self):
        """Los estados de contacto empiezan en 40."""
        assert States.CONTACTO_SELECT == 40
        assert States.CONTACTO_FIELD == 41
        assert States.CONTACTO_VALUE == 42
        assert States.CONTACTO_CONFIRMATION == 43

    def test_timeout_is_negative(self):
        """El estado TIMEOUT es -1."""
        assert States.TIMEOUT == -1

    def test_no_state_overlap(self):
        """Ningún par de estados tiene el mismo valor."""
        all_states = [
            States.CREAR_DESCRIPTION,
            States.CREAR_DATE,
            States.CREAR_TIME_SLOT,
            States.CREAR_CONFIRMATION,
            States.EDITAR_SELECT,
            States.EDITAR_CHANGES,
            States.EDITAR_CONFIRMATION,
            States.ELIMINAR_SELECT,
            States.ELIMINAR_CONFIRMATION,
            States.TERMINAR_SELECT,
            States.TERMINAR_CLOSURE,
            States.TERMINAR_PHOTOS,
            States.TERMINAR_CONFIRMATION,
            States.CONTACTO_SELECT,
            States.CONTACTO_FIELD,
            States.CONTACTO_VALUE,
            States.CONTACTO_CONFIRMATION,
            States.TIMEOUT,
        ]
        assert len(all_states) == len(set(all_states))


# ── CallbackData ──────────────────────────────────────────────────────────────


class TestCallbackData:
    """Tests para los patrones de callback_data."""

    def test_menu_actions_defined(self):
        """Todos los callbacks de menú principal están definidos."""
        assert CallbackData.CREAR_EVENTO == "crear_evento"
        assert CallbackData.EDITAR_EVENTO == "editar_evento"
        assert CallbackData.VER_EVENTOS == "ver_eventos"
        assert CallbackData.ELIMINAR_EVENTO == "eliminar_evento"
        assert CallbackData.TERMINAR_EVENTO == "terminar_evento"
        assert CallbackData.VER_CONTACTOS == "ver_contactos"
        assert CallbackData.EDITAR_CONTACTO == "editar_contacto"

    def test_confirmation_callbacks(self):
        """Los callbacks de confirmación están definidos."""
        assert CallbackData.CONFIRM_YES == "confirm_yes"
        assert CallbackData.CONFIRM_NO == "confirm_no"

    def test_cancel_callback(self):
        """El callback de cancelar está definido."""
        assert CallbackData.CANCEL == "cancel"

    def test_prefixes_defined(self):
        """Los prefijos de selección están definidos."""
        assert CallbackData.EVENT_PREFIX == "event_"
        assert CallbackData.CONTACT_PREFIX == "contact_"
        assert CallbackData.SLOT_PREFIX == "slot_"
        assert CallbackData.FIELD_PREFIX == "field_"

    def test_field_callbacks(self):
        """Los callbacks de campos editables de contacto están definidos."""
        assert CallbackData.FIELD_NOMBRE == "field_nombre"
        assert CallbackData.FIELD_TELEFONO == "field_telefono"
        assert CallbackData.FIELD_DIRECCION == "field_direccion"
        assert CallbackData.FIELD_NOTAS == "field_notas"

    def test_photos_callbacks(self):
        """Los callbacks de fotos están definidos."""
        assert CallbackData.PHOTOS_DONE == "photos_done"
        assert CallbackData.PHOTOS_SKIP == "photos_skip"

    def test_slot_confirm(self):
        """El callback de confirmar slot está definido."""
        assert CallbackData.SLOT_CONFIRM == "slot_confirm"

    def test_noop_callback(self):
        """El callback noop (paginación) está definido."""
        assert CallbackData.NOOP == "noop"


# ── SERVICE_EMOJIS ────────────────────────────────────────────────────────────


class TestServiceEmojis:
    """Tests para el mapeo de emojis por tipo de servicio."""

    def test_all_tipos_have_emoji(self):
        """Cada TipoServicio tiene un emoji asignado."""
        for tipo in TipoServicio:
            assert tipo in SERVICE_EMOJIS

    def test_emojis_are_strings(self):
        """Todos los emojis son strings no vacíos."""
        for emoji in SERVICE_EMOJIS.values():
            assert isinstance(emoji, str)
            assert len(emoji) > 0

    def test_instalacion_emoji(self):
        assert SERVICE_EMOJIS[TipoServicio.INSTALACION] == "🔵"

    def test_revision_emoji(self):
        assert SERVICE_EMOJIS[TipoServicio.REVISION] == "🟡"

    def test_otro_emoji(self):
        assert SERVICE_EMOJIS[TipoServicio.OTRO] == "⚪"


# ── get_service_emoji ─────────────────────────────────────────────────────────


class TestGetServiceEmoji:
    """Tests para la función get_service_emoji()."""

    def test_with_enum(self):
        """Recibe un TipoServicio y retorna el emoji correcto."""
        assert get_service_emoji(TipoServicio.INSTALACION) == "🔵"

    def test_with_valid_string(self):
        """Recibe un string válido y retorna el emoji correcto."""
        assert get_service_emoji("instalacion") == "🔵"

    def test_with_invalid_string(self):
        """Recibe un string inválido y retorna el emoji por defecto."""
        assert get_service_emoji("no_existe") == "⚪"

    def test_with_otro(self):
        """El tipo OTRO retorna el emoji por defecto."""
        assert get_service_emoji(TipoServicio.OTRO) == "⚪"


# ── Messages ──────────────────────────────────────────────────────────────────


class TestMessages:
    """Tests para los textos centralizados del bot."""

    def test_welcome_has_placeholder(self):
        """El mensaje de bienvenida tiene placeholder {nombre}."""
        assert "{nombre}" in Messages.WELCOME

    def test_welcome_formats_correctly(self):
        """El mensaje de bienvenida se formatea con un nombre."""
        result = Messages.WELCOME.format(nombre="Juan")
        assert "Juan" in result

    def test_menu_header_is_markdown(self):
        """El encabezado del menú usa Markdown."""
        assert "*" in Messages.MENU_HEADER

    def test_ask_new_value_has_placeholder(self):
        """El mensaje ASK_NEW_VALUE tiene placeholder {campo}."""
        assert "{campo}" in Messages.ASK_NEW_VALUE

    def test_error_generic_has_placeholder(self):
        """El mensaje ERROR_GENERIC tiene placeholder {error}."""
        assert "{error}" in Messages.ERROR_GENERIC

    def test_conversation_timeout_mentions_menu(self):
        """El mensaje de timeout menciona /menu."""
        assert "/menu" in Messages.CONVERSATION_TIMEOUT

    def test_permission_denied_has_emoji(self):
        """El mensaje de permiso denegado tiene emoji."""
        assert "🚫" in Messages.PERMISSION_DENIED

    def test_not_authorized_has_emoji(self):
        """El mensaje de no autorizado tiene emoji."""
        assert "🚫" in Messages.NOT_AUTHORIZED


# ── Constantes de configuración ───────────────────────────────────────────────


class TestConfigConstants:
    """Tests para constantes de configuración del bot."""

    def test_telegram_max_length(self):
        """El límite de Telegram es 4096 caracteres."""
        assert TELEGRAM_MAX_LENGTH == 4096

    def test_items_per_page(self):
        """Items por página es 5."""
        assert ITEMS_PER_PAGE == 5

    def test_items_per_page_is_positive(self):
        """Items por página es un entero positivo."""
        assert isinstance(ITEMS_PER_PAGE, int)
        assert ITEMS_PER_PAGE > 0
