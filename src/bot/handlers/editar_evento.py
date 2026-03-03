# src/bot/handlers/editar_evento.py
"""ConversationHandler para la edición de eventos."""

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
WAITING_SELECT = States.EDITAR_SELECT
WAITING_CHANGES = States.EDITAR_CHANGES
WAITING_CONFIRMATION = States.EDITAR_CONFIRMATION


@require_role("admin", "editor")
async def start_editar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de edición mostrando la lista de eventos pendientes."""
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
        action="editar",
        clientes=clientes_dict,
    )
    await query.edit_message_text(
        Messages.SELECT_EVENT_EDIT,
        reply_markup=keyboard,
    )
    return WAITING_SELECT


@require_role("admin", "editor")
async def select_evento(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """El usuario seleccionó un evento para editar."""
    query = update.callback_query
    await query.answer()

    # Guardar chat_id (puede ser entry point directo desde natural.py)
    context.user_data["chat_id"] = update.effective_chat.id

    evento_id = int(query.data.replace("editar_", ""))
    orchestrator = context.bot_data["orchestrator"]

    evento = await orchestrator.repo.get_evento_by_id(evento_id)
    if not evento:
        await query.edit_message_text("❌ Evento no encontrado.")
        return ConversationHandler.END

    context.user_data["editing_evento_id"] = evento_id
    context.user_data["editing_evento"] = evento

    cliente = await orchestrator.repo.get_cliente_by_id(evento.cliente_id)
    detail = format_event_detail(evento, cliente)

    await query.edit_message_text(
        f"{detail}\n\n{Messages.DESCRIBE_CHANGES}",
        parse_mode="Markdown",
    )
    return WAITING_CHANGES


async def receive_changes(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Recibe la descripción de cambios en lenguaje natural."""
    orchestrator = context.bot_data["orchestrator"]
    evento = context.user_data.get("editing_evento")

    if not evento:
        await update.message.reply_text("❌ Error: no se encontró el evento.")
        return ConversationHandler.END

    result = await orchestrator.edit_event_from_text(
        text=update.message.text,
        evento=evento,
        user_id=update.effective_user.id,
    )

    if result.ok:
        context.user_data["pending_changes"] = result.data
        # Mostrar resumen de cambios y pedir confirmación
        changes_text = _format_changes(result.data)
        keyboard = build_confirmation_keyboard()
        await update.message.reply_text(
            f"✏️ *Cambios a aplicar:*\n\n{changes_text}\n\n¿Confirmás los cambios?",
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        return WAITING_CONFIRMATION

    if result.needs_input:
        await update.message.reply_text(result.question or Messages.DESCRIBE_CHANGES)
        return WAITING_CHANGES

    await update.message.reply_text(f"❌ {result.message}")
    return ConversationHandler.END


async def confirm_edit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Confirma y aplica los cambios al evento."""
    query = update.callback_query
    await query.answer()

    orchestrator = context.bot_data["orchestrator"]
    evento_id = context.user_data.get("editing_evento_id")
    changes = context.user_data.get("pending_changes", {})

    result = await orchestrator.apply_event_changes(
        evento_id=evento_id,
        changes=changes,
    )

    if result.ok:
        await query.edit_message_text(Messages.EVENT_UPDATED)
    else:
        await query.edit_message_text(f"❌ {result.message}")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_edit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Cancela la edición."""
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


def _format_changes(changes: dict) -> str:
    """Formatea los cambios para mostrar al usuario."""
    if not changes:
        return "Sin cambios detectados."
    lines = []
    for field, value in changes.items():
        lines.append(f"• *{field}*: {value}")
    return "\n".join(lines)


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
    """Retorna el ConversationHandler para editar eventos."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                start_editar,
                pattern=f"^{CallbackData.EDITAR_EVENTO}$",
            ),
            # Entry point directo: cuando natural.py muestra la lista de eventos
            # y el usuario presiona un botón editar_{id}
            CallbackQueryHandler(select_evento, pattern=r"^editar_\d+$"),
        ],
        states={
            WAITING_SELECT: [
                CallbackQueryHandler(select_evento, pattern=r"^editar_\d+$"),
            ],
            WAITING_CHANGES: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER,
                    receive_changes,
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
