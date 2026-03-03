# tests/unit/test_middleware.py
"""Tests para el módulo de middleware de permisos del bot."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.constants import Messages
from src.bot.middleware import get_user_role, require_authorized, require_role
from src.db.models import Rol

from telegram.ext import ConversationHandler


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_settings(admin_ids: list[int] = None, editor_ids: list[int] = None):
    """Crea un mock de Settings con IDs configurados."""
    settings = MagicMock()
    settings.admin_telegram_ids = admin_ids or [100, 101]
    settings.editor_telegram_ids = editor_ids or [200, 201]
    return settings


def _mock_update(user_id: int, is_callback: bool = False):
    """Crea un mock de Update de Telegram."""
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id

    if is_callback:
        update.callback_query = AsyncMock()
        update.callback_query.answer = AsyncMock()
        update.message = None
    else:
        update.callback_query = None
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()

    return update


def _mock_context():
    """Crea un mock de ContextTypes.DEFAULT_TYPE."""
    return MagicMock()


# ── get_user_role ─────────────────────────────────────────────────────────────


class TestGetUserRole:
    """Tests para get_user_role()."""

    @patch("src.bot.middleware.get_settings")
    def test_admin_returns_admin(self, mock_get_settings):
        """Un ID en admin_telegram_ids retorna 'admin'."""
        mock_get_settings.return_value = _mock_settings(admin_ids=[100])
        assert get_user_role(100) == Rol.ADMIN.value

    @patch("src.bot.middleware.get_settings")
    def test_editor_returns_editor(self, mock_get_settings):
        """Un ID en editor_telegram_ids retorna 'editor'."""
        mock_get_settings.return_value = _mock_settings(editor_ids=[200])
        assert get_user_role(200) == Rol.EDITOR.value

    @patch("src.bot.middleware.get_settings")
    def test_unknown_returns_none(self, mock_get_settings):
        """Un ID que no está en ninguna lista retorna None."""
        mock_get_settings.return_value = _mock_settings()
        assert get_user_role(999) is None

    @patch("src.bot.middleware.get_settings")
    def test_admin_takes_priority(self, mock_get_settings):
        """Si un ID está en ambas listas, admin tiene prioridad."""
        mock_get_settings.return_value = _mock_settings(
            admin_ids=[100],
            editor_ids=[100],
        )
        assert get_user_role(100) == Rol.ADMIN.value


# ── require_role ──────────────────────────────────────────────────────────────


class TestRequireRole:
    """Tests para el decorador require_role()."""

    @pytest.mark.asyncio
    @patch("src.bot.middleware.get_settings")
    async def test_admin_allowed_for_admin_role(self, mock_get_settings):
        """Un admin puede ejecutar handlers con @require_role('admin')."""
        mock_get_settings.return_value = _mock_settings(admin_ids=[100])

        @require_role("admin")
        async def handler(update, context):
            return "executed"

        update = _mock_update(user_id=100)
        context = _mock_context()
        result = await handler(update, context)
        assert result == "executed"

    @pytest.mark.asyncio
    @patch("src.bot.middleware.get_settings")
    async def test_editor_denied_for_admin_role(self, mock_get_settings):
        """Un editor NO puede ejecutar handlers con @require_role('admin')."""
        mock_get_settings.return_value = _mock_settings(editor_ids=[200])

        @require_role("admin")
        async def handler(update, context):
            return "executed"

        update = _mock_update(user_id=200)
        context = _mock_context()
        result = await handler(update, context)
        assert result == ConversationHandler.END  # El handler no se ejecutó
        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.bot.middleware.get_settings")
    async def test_editor_allowed_for_editor_role(self, mock_get_settings):
        """Un editor puede ejecutar handlers con @require_role('admin', 'editor')."""
        mock_get_settings.return_value = _mock_settings(editor_ids=[200])

        @require_role("admin", "editor")
        async def handler(update, context):
            return "executed"

        update = _mock_update(user_id=200)
        context = _mock_context()
        result = await handler(update, context)
        assert result == "executed"

    @pytest.mark.asyncio
    @patch("src.bot.middleware.get_settings")
    async def test_unauthorized_user_denied(self, mock_get_settings):
        """Un usuario no autorizado es denegado."""
        mock_get_settings.return_value = _mock_settings()

        @require_role("admin")
        async def handler(update, context):
            return "executed"

        update = _mock_update(user_id=999)
        context = _mock_context()
        result = await handler(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    @patch("src.bot.middleware.get_settings")
    async def test_denied_via_callback_query(self, mock_get_settings):
        """Denegación via callback query usa answer() con show_alert."""
        mock_get_settings.return_value = _mock_settings()

        @require_role("admin")
        async def handler(update, context):
            return "executed"

        update = _mock_update(user_id=999, is_callback=True)
        context = _mock_context()
        await handler(update, context)
        update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.bot.middleware.get_settings")
    async def test_denied_message_text(self, mock_get_settings):
        """Denegación por rol incorrecto envía PERMISSION_DENIED."""
        mock_get_settings.return_value = _mock_settings(editor_ids=[200])

        @require_role("admin")
        async def handler(update, context):
            return "executed"

        update = _mock_update(user_id=200)
        context = _mock_context()
        await handler(update, context)
        call_args = update.message.reply_text.call_args
        assert Messages.PERMISSION_DENIED in str(call_args)

    @pytest.mark.asyncio
    @patch("src.bot.middleware.get_settings")
    async def test_no_effective_user_returns_none(self, mock_get_settings):
        """Sin effective_user, el handler no se ejecuta."""
        mock_get_settings.return_value = _mock_settings()

        @require_role("admin")
        async def handler(update, context):
            return "executed"

        update = MagicMock()
        update.effective_user = None
        context = _mock_context()
        result = await handler(update, context)
        assert result == ConversationHandler.END


# ── require_authorized ────────────────────────────────────────────────────────


class TestRequireAuthorized:
    """Tests para el decorador require_authorized."""

    @pytest.mark.asyncio
    @patch("src.bot.middleware.get_settings")
    async def test_admin_is_authorized(self, mock_get_settings):
        """Un admin está autorizado."""
        mock_get_settings.return_value = _mock_settings(admin_ids=[100])

        @require_authorized
        async def handler(update, context):
            return "executed"

        update = _mock_update(user_id=100)
        context = _mock_context()
        result = await handler(update, context)
        assert result == "executed"

    @pytest.mark.asyncio
    @patch("src.bot.middleware.get_settings")
    async def test_editor_is_authorized(self, mock_get_settings):
        """Un editor está autorizado."""
        mock_get_settings.return_value = _mock_settings(editor_ids=[200])

        @require_authorized
        async def handler(update, context):
            return "executed"

        update = _mock_update(user_id=200)
        context = _mock_context()
        result = await handler(update, context)
        assert result == "executed"

    @pytest.mark.asyncio
    @patch("src.bot.middleware.get_settings")
    async def test_unknown_user_denied(self, mock_get_settings):
        """Un usuario desconocido es denegado."""
        mock_get_settings.return_value = _mock_settings()

        @require_authorized
        async def handler(update, context):
            return "executed"

        update = _mock_update(user_id=999)
        context = _mock_context()
        result = await handler(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    @patch("src.bot.middleware.get_settings")
    async def test_unauthorized_sends_not_authorized(self, mock_get_settings):
        """Usuario no autorizado recibe mensaje NOT_AUTHORIZED."""
        mock_get_settings.return_value = _mock_settings()

        @require_authorized
        async def handler(update, context):
            return "executed"

        update = _mock_update(user_id=999)
        context = _mock_context()
        await handler(update, context)
        call_args = update.message.reply_text.call_args
        assert Messages.NOT_AUTHORIZED in str(call_args)

    @pytest.mark.asyncio
    @patch("src.bot.middleware.get_settings")
    async def test_no_effective_user_returns_none(self, mock_get_settings):
        """Sin effective_user, el handler no se ejecuta."""
        mock_get_settings.return_value = _mock_settings()

        @require_authorized
        async def handler(update, context):
            return "executed"

        update = MagicMock()
        update.effective_user = None
        context = _mock_context()
        result = await handler(update, context)
        assert result == ConversationHandler.END
