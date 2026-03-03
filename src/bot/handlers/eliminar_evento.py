# src/bot/handlers/eliminar_evento.py
"""ConversationHandler para la eliminación de eventos."""

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
from src.bot.formatters import format_event_detail
from src.bot.keyboards import build_confirmation_keyboard, build_event_list_keyboard
from src.bot.middleware import require_role
from src.bot.handlers.start import MENU_BUTTON_FILTER, menu_fallback
from src.db.models import Cliente

logger = logging.getLogger(__name__)

# Estados locales
WAITING_SELECT = States.ELIMINAR_SELECT
WAITING_CONFIRMATION = States.ELIMINAR_CONFIRMATION


@require_role("admin")
async def start_eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de eliminación mostrando la lista de eventos pendientes."""
    query = update.callback_query
    await query.answer()

    context.user_data["chat_id"] = update.effective_chat.id

    orchestrator = context.bot_data["orchestrator"]
    eventos = await orchestrator.repo.list_eventos_pendientes()

    if not eventos:
        await query.edit_message_text(Messages.NO_PENDING_EVENTS)
        return ConversationHandler.END

    clientes_dict = await _build_clientes_dict(orchestrator, eventos)
    keyboard = build_event_list_keyboard(
        eventos,
        action="eliminar",
        clientes=clientes_dict,
    )
    await query.edit_message_text(
        Messages.SELECT_EVENT_DELETE,
        reply_markup=keyboard,
    )
    return WAITING_SELECT


@require_role("admin")
async def select_evento(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """El usuario seleccionó un evento para eliminar."""
    query = update.callback_query
    await query.answer()

    # Guardar chat_id (puede ser entry point directo desde natural.py)
    context.user_data["chat_id"] = update.effective_chat.id

    evento_id = int(query.data.replace("eliminar_", ""))
    orchestrator = context.bot_data["orchestrator"]

    evento = await orchestrator.repo.get_evento_by_id(evento_id)
    if not evento:
        await query.edit_message_text("❌ Evento no encontrado.")
        return ConversationHandler.END

    context.user_data["deleting_evento_id"] = evento_id

    cliente = await orchestrator.repo.get_cliente_by_id(evento.cliente_id)
    detail = format_event_detail(evento, cliente)

    keyboard = build_confirmation_keyboard()
    await query.edit_message_text(
        f"{detail}\n\n{Messages.CONFIRM_DELETE}",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return WAITING_CONFIRMATION


async def confirm_delete(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Confirma y ejecuta la eliminación del evento."""
    query = update.callback_query
    await query.answer()

    orchestrator = context.bot_data["orchestrator"]
    evento_id = context.user_data.get("deleting_evento_id")

    result = await orchestrator.delete_event(evento_id)

    if result.ok:
        await query.edit_message_text(Messages.EVENT_DELETED)
    else:
        await query.edit_message_text(f"❌ {result.message}")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_delete(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Cancela la eliminación."""
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


async def _build_clientes_dict(orchestrator, eventos) -> dict[int, Cliente]:
    """Construye un diccionario id->Cliente para los eventos dados."""
    clientes_dict: dict[int, Cliente] = {}
    seen_ids: set[int] = set()
    for ev in eventos:
        if ev.cliente_id not in seen_ids:
            seen_ids.add(ev.cliente_id)
            cliente = await orchestrator.repo.get_cliente_by_id(ev.cliente_id)
            if cliente:
                clientes_dict[ev.cliente_id] = cliente
    return clientes_dict


def get_conversation_handler() -> ConversationHandler:
    """Retorna el ConversationHandler para eliminar eventos."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                start_eliminar,
                pattern=f"^{CallbackData.ELIMINAR_EVENTO}$",
            ),
            # Entry point directo: cuando natural.py muestra la lista de eventos
            # y el usuario presiona un botón eliminar_{id}
            CallbackQueryHandler(select_evento, pattern=r"^eliminar_\d+$"),
        ],
        states={
            WAITING_SELECT: [
                CallbackQueryHandler(select_evento, pattern=r"^eliminar_\d+$"),
            ],
            WAITING_CONFIRMATION: [
                CallbackQueryHandler(
                    confirm_delete,
                    pattern=f"^{CallbackData.CONFIRM_YES}$",
                ),
                CallbackQueryHandler(
                    cancel_delete,
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
            CallbackQueryHandler(cancel_delete, pattern=f"^{CallbackData.CANCEL}$"),
        ],
        conversation_timeout=300,
    )
