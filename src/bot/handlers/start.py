# src/bot/handlers/start.py
"""Handlers para /start, /menu y botón persistente — menú principal del bot."""

import logging

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.bot.constants import CallbackData, Messages
from src.bot.keyboards import build_main_menu, build_persistent_menu
from src.bot.middleware import get_user_role, require_authorized

logger = logging.getLogger(__name__)


@require_authorized
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /start. Muestra bienvenida y menú principal.

    Envía primero el ReplyKeyboardMarkup persistente y luego el menú inline.
    """
    user = update.effective_user
    nombre = user.first_name or "usuario"
    role = get_user_role(user.id)

    welcome = Messages.WELCOME.format(nombre=nombre)
    keyboard = build_main_menu(role)
    persistent = build_persistent_menu()

    # Enviar el teclado persistente (Reply) con la bienvenida
    await update.message.reply_text(
        welcome,
        reply_markup=persistent,
        parse_mode="Markdown",
    )

    # Enviar el menú inline como segundo mensaje
    await update.message.reply_text(
        Messages.MENU_HEADER,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


@require_authorized
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /menu. Muestra el menú principal."""
    user = update.effective_user
    role = get_user_role(user.id)
    keyboard = build_main_menu(role)

    await update.message.reply_text(
        Messages.MENU_HEADER,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


@require_authorized
async def menu_text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handler para el botón persistente '📋 Menú'.

    Se activa cuando el usuario pulsa el botón de ReplyKeyboard.
    Muestra el menú inline principal.
    """
    user = update.effective_user
    role = get_user_role(user.id)
    keyboard = build_main_menu(role)

    await update.message.reply_text(
        Messages.MENU_HEADER,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


@require_authorized
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el botón de volver al menú principal."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    role = get_user_role(user.id)
    keyboard = build_main_menu(role)

    await query.edit_message_text(
        Messages.MENU_HEADER,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


# Filtro reutilizable para el texto del botón persistente "📋 Menú"
MENU_BUTTON_FILTER = filters.TEXT & filters.Regex(r"^📋 Menú$")


async def menu_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fallback para ConversationHandlers: al pulsar '📋 Menú' sale de la
    conversación activa y muestra el menú principal.

    Returns:
        ConversationHandler.END para terminar la conversación.
    """
    from telegram.ext import ConversationHandler

    user = update.effective_user
    role = get_user_role(user.id) if user else None

    if role:
        keyboard = build_main_menu(role)
        await update.message.reply_text(
            Messages.MENU_HEADER,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    context.user_data.clear()
    return ConversationHandler.END


def get_start_handlers() -> list:
    """Retorna los handlers de /start y /menu.

    NOTA: El handler para el botón persistente "📋 Menú" (menu_text_handler)
    NO se incluye aquí. Se registra POR SEPARADO en app.py DESPUÉS de todos
    los ConversationHandlers para que los fallbacks de las conversaciones
    tengan prioridad y puedan cerrar la conversación activa antes de que
    el handler global lo capture.

    Returns:
        Lista de handlers para registrar en la Application.
    """
    return [
        CommandHandler("start", start_command),
        CommandHandler("menu", menu_command),
        CallbackQueryHandler(menu_callback, pattern="^menu$"),
    ]
