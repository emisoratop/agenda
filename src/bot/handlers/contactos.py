# src/bot/handlers/contactos.py
"""Handlers para ver y editar contactos."""

import logging

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.bot.constants import CallbackData, Messages, States
from src.bot.formatters import format_contacts_list, split_message
from src.bot.keyboards import (
    build_confirmation_keyboard,
    build_contact_list_keyboard,
    build_field_selection_keyboard,
    build_pagination_keyboard,
    paginate_items,
)
from src.bot.middleware import require_authorized, require_role
from src.bot.handlers.start import MENU_BUTTON_FILTER, menu_fallback

logger = logging.getLogger(__name__)

# Estados para edición de contactos
WAITING_SELECT = States.CONTACTO_SELECT
WAITING_FIELD = States.CONTACTO_FIELD
WAITING_VALUE = States.CONTACTO_VALUE
WAITING_CONFIRMATION = States.CONTACTO_CONFIRMATION

# Mapeo de callback_data a nombre de campo
_FIELD_MAP = {
    CallbackData.FIELD_NOMBRE: "nombre",
    CallbackData.FIELD_TELEFONO: "telefono",
    CallbackData.FIELD_DIRECCION: "direccion",
    CallbackData.FIELD_NOTAS: "notas",
}


@require_authorized
async def ver_contactos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra la lista de contactos (acción inmediata, sin estados)."""
    query = update.callback_query
    await query.answer()

    orchestrator = context.bot_data["orchestrator"]
    clientes = await orchestrator.repo.list_clientes()

    if not clientes:
        await query.edit_message_text(Messages.NO_CONTACTS)
        return

    # Paginar
    page = 0
    page_items, total_pages = paginate_items(clientes, page)
    text = format_contacts_list(page_items)
    keyboard = build_pagination_keyboard(page, total_pages, "cli_page")

    parts = split_message(text)
    for i, part in enumerate(parts):
        if i == len(parts) - 1 and keyboard:
            await query.edit_message_text(
                part,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        elif i == 0:
            await query.edit_message_text(part, parse_mode="Markdown")
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=part,
                parse_mode="Markdown",
            )


async def handle_contactos_pagination(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Maneja clicks en botones de paginación de contactos."""
    query = update.callback_query
    await query.answer()

    _, page_str = query.data.rsplit(":", 1)
    page = int(page_str)

    orchestrator = context.bot_data["orchestrator"]
    clientes = await orchestrator.repo.list_clientes()

    if not clientes:
        await query.edit_message_text(Messages.NO_CONTACTS)
        return

    page_items, total_pages = paginate_items(clientes, page)
    text = format_contacts_list(page_items)
    keyboard = build_pagination_keyboard(page, total_pages, "cli_page")

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ── Flujo de edición de contactos ─────────────────────────────────────────────


@require_role("admin")
async def start_editar_contacto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Inicia el flujo de edición de contacto."""
    query = update.callback_query
    await query.answer()

    context.user_data["chat_id"] = update.effective_chat.id

    orchestrator = context.bot_data["orchestrator"]
    clientes = await orchestrator.repo.list_clientes()

    if not clientes:
        await query.edit_message_text(Messages.NO_CONTACTS)
        return ConversationHandler.END

    keyboard = build_contact_list_keyboard(clientes)
    await query.edit_message_text(
        Messages.SELECT_CONTACT,
        reply_markup=keyboard,
    )
    return WAITING_SELECT


@require_role("admin")
async def select_contacto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """El usuario seleccionó un contacto para editar."""
    query = update.callback_query
    await query.answer()

    # Guardar chat_id (puede ser entry point directo desde natural.py)
    context.user_data["chat_id"] = update.effective_chat.id

    contact_id = int(query.data.replace(CallbackData.CONTACT_PREFIX, ""))
    orchestrator = context.bot_data["orchestrator"]

    cliente = await orchestrator.repo.get_cliente_by_id(contact_id)
    if not cliente:
        await query.edit_message_text("❌ Contacto no encontrado.")
        return ConversationHandler.END

    context.user_data["editing_contact_id"] = contact_id
    context.user_data["editing_contact"] = cliente

    keyboard = build_field_selection_keyboard()
    await query.edit_message_text(
        f"👤 *{cliente.nombre}*\n\n{Messages.SELECT_FIELD}",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return WAITING_FIELD


async def select_field(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """El usuario seleccionó qué campo editar."""
    query = update.callback_query
    await query.answer()

    field_name = _FIELD_MAP.get(query.data)
    if not field_name:
        await query.edit_message_text("❌ Campo no válido.")
        return ConversationHandler.END

    context.user_data["editing_field"] = field_name

    await query.edit_message_text(
        Messages.ASK_NEW_VALUE.format(campo=field_name.capitalize()),
        parse_mode="Markdown",
    )
    return WAITING_VALUE


async def receive_value(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Recibe el nuevo valor para el campo seleccionado."""
    new_value = update.message.text
    field_name = context.user_data.get("editing_field")
    contact = context.user_data.get("editing_contact")

    context.user_data["new_value"] = new_value

    keyboard = build_confirmation_keyboard()
    await update.message.reply_text(
        f"✏️ *Confirmar cambio*\n\n"
        f"👤 Contacto: {contact.nombre}\n"
        f"📋 Campo: {field_name.capitalize()}\n"
        f"📝 Nuevo valor: {new_value}\n\n"
        f"¿Confirmás el cambio?",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return WAITING_CONFIRMATION


async def confirm_edit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Confirma y aplica el cambio al contacto."""
    query = update.callback_query
    await query.answer()

    orchestrator = context.bot_data["orchestrator"]
    contact_id = context.user_data.get("editing_contact_id")
    field_name = context.user_data.get("editing_field")
    new_value = context.user_data.get("new_value")

    success = await orchestrator.repo.update_cliente(
        contact_id,
        **{field_name: new_value},
    )

    if success:
        await query.edit_message_text(Messages.CONTACT_UPDATED)
    else:
        await query.edit_message_text("❌ No se pudo actualizar el contacto.")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_edit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Cancela la edición de contacto."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(Messages.OPERATION_CANCELLED)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handler de /cancel para salir de la conversación."""
    await update.message.reply_text(Messages.OPERATION_CANCELLED)
    context.user_data.clear()
    return ConversationHandler.END


async def timeout_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handler de timeout para conversaciones abandonadas."""
    chat_id = context.user_data.get("chat_id")
    if chat_id:
        await context.bot.send_message(
            chat_id=chat_id,
            text=Messages.CONVERSATION_TIMEOUT,
        )
    context.user_data.clear()
    return ConversationHandler.END


def get_ver_contactos_handlers() -> list:
    """Retorna los handlers para ver contactos.

    Returns:
        Lista de handlers para registrar en la Application.
    """
    return [
        CallbackQueryHandler(
            ver_contactos,
            pattern=f"^{CallbackData.VER_CONTACTOS}$",
        ),
        CallbackQueryHandler(
            handle_contactos_pagination,
            pattern=r"^cli_page:\d+$",
        ),
    ]


def get_editar_contacto_handler() -> ConversationHandler:
    """Retorna el ConversationHandler para editar contactos."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                start_editar_contacto,
                pattern=f"^{CallbackData.EDITAR_CONTACTO}$",
            ),
            # Entry point directo: cuando natural.py muestra la lista de contactos
            # y el usuario presiona un botón contact_{id}
            CallbackQueryHandler(
                select_contacto,
                pattern=f"^{CallbackData.CONTACT_PREFIX}\\d+$",
            ),
        ],
        states={
            WAITING_SELECT: [
                CallbackQueryHandler(
                    select_contacto,
                    pattern=f"^{CallbackData.CONTACT_PREFIX}\\d+$",
                ),
            ],
            WAITING_FIELD: [
                CallbackQueryHandler(
                    select_field,
                    pattern=f"^{CallbackData.FIELD_PREFIX}",
                ),
            ],
            WAITING_VALUE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER,
                    receive_value,
                ),
            ],
            WAITING_CONFIRMATION: [
                CallbackQueryHandler(
                    confirm_edit,
                    pattern=f"^{CallbackData.CONFIRM_YES}$",
                ),
                CallbackQueryHandler(
                    cancel_edit,
                    pattern=f"^{CallbackData.CONFIRM_NO}$",
                ),
            ],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, timeout_handler),
                CallbackQueryHandler(timeout_handler),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
            MessageHandler(MENU_BUTTON_FILTER, menu_fallback),
            CallbackQueryHandler(cancel_edit, pattern=f"^{CallbackData.CANCEL}$"),
        ],
        conversation_timeout=300,
    )
