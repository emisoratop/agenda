# src/bot/handlers/terminar_evento.py
"""ConversationHandler para el cierre/completar de eventos."""

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
from src.bot.formatters import format_closure_confirmation, format_event_detail
from src.bot.keyboards import (
    build_confirmation_keyboard,
    build_event_list_keyboard,
    build_photos_keyboard,
)
from src.bot.middleware import require_role
from src.bot.handlers.start import MENU_BUTTON_FILTER, menu_fallback
from src.db.models import Cliente

logger = logging.getLogger(__name__)

# Estados locales
WAITING_SELECT = States.TERMINAR_SELECT
WAITING_CLOSURE = States.TERMINAR_CLOSURE
WAITING_PHOTOS = States.TERMINAR_PHOTOS
WAITING_CONFIRMATION = States.TERMINAR_CONFIRMATION


@require_role("admin", "editor")
async def start_terminar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de cierre mostrando la lista de eventos pendientes."""
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
        action="terminar",
        clientes=clientes_dict,
    )
    await query.edit_message_text(
        Messages.SELECT_EVENT_COMPLETE,
        reply_markup=keyboard,
    )
    return WAITING_SELECT


@require_role("admin", "editor")
async def select_evento(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """El usuario seleccionó un evento para cerrar."""
    query = update.callback_query
    await query.answer()

    # Guardar chat_id (puede ser entry point directo desde natural.py)
    context.user_data["chat_id"] = update.effective_chat.id

    evento_id = int(query.data.replace("terminar_", ""))
    orchestrator = context.bot_data["orchestrator"]

    evento = await orchestrator.repo.get_evento_by_id(evento_id)
    if not evento:
        await query.edit_message_text("❌ Evento no encontrado.")
        return ConversationHandler.END

    context.user_data["completing_evento_id"] = evento_id
    context.user_data["completing_evento"] = evento

    cliente = await orchestrator.repo.get_cliente_by_id(evento.cliente_id)
    detail = format_event_detail(evento, cliente)

    await query.edit_message_text(
        f"{detail}\n\n{Messages.DESCRIBE_CLOSURE}",
        parse_mode="Markdown",
    )
    return WAITING_CLOSURE


async def receive_closure(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Recibe la descripción del cierre en lenguaje natural."""
    orchestrator = context.bot_data["orchestrator"]

    result = await orchestrator.parse_closure_text(
        text=update.message.text,
    )

    if result.ok:
        context.user_data["closure_data"] = result.data
        context.user_data["photos"] = []

        # Preguntar por fotos
        keyboard = build_photos_keyboard()
        await update.message.reply_text(
            Messages.ASK_PHOTOS,
            reply_markup=keyboard,
        )
        return WAITING_PHOTOS

    if result.needs_input:
        await update.message.reply_text(
            result.question or Messages.DESCRIBE_CLOSURE,
        )
        return WAITING_CLOSURE

    await update.message.reply_text(f"❌ {result.message}")
    return ConversationHandler.END


async def receive_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Recibe una foto adjunta al cierre del servicio."""
    photo = update.message.photo[-1]  # La foto de mayor resolución
    file = await context.bot.get_file(photo.file_id)

    photos = context.user_data.get("photos", [])
    photos.append(file.file_path)
    context.user_data["photos"] = photos

    keyboard = build_photos_keyboard()
    await update.message.reply_text(
        f"📸 Foto {len(photos)} recibida. Enviá más o presioná un botón.",
        reply_markup=keyboard,
    )
    return WAITING_PHOTOS


async def photos_done(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """El usuario terminó de enviar fotos."""
    query = update.callback_query
    await query.answer()

    evento = context.user_data.get("completing_evento")
    closure_data = context.user_data.get("closure_data", {})
    photos = context.user_data.get("photos", [])

    # Agregar fotos al closure_data
    if photos:
        closure_data["fotos"] = photos

    context.user_data["closure_data"] = closure_data

    # Mostrar resumen de cierre
    orchestrator = context.bot_data["orchestrator"]
    cliente = await orchestrator.repo.get_cliente_by_id(evento.cliente_id)

    # Crear un evento temporal con datos de cierre para formatear
    summary_lines = [f"📋 *Resumen del cierre*\n"]
    if closure_data.get("trabajo_realizado"):
        summary_lines.append(
            f"🔧 Trabajo: {closure_data['trabajo_realizado']}",
        )
    if closure_data.get("monto_cobrado") is not None:
        summary_lines.append(
            f"💰 Monto: ${closure_data['monto_cobrado']:,.0f}",
        )
    if closure_data.get("notas_cierre"):
        summary_lines.append(
            f"📝 Notas: {closure_data['notas_cierre']}",
        )
    if photos:
        summary_lines.append(f"📸 Fotos: {len(photos)} adjuntada(s)")

    summary_lines.append("\n¿Confirmás el cierre del servicio?")

    keyboard = build_confirmation_keyboard()
    await query.edit_message_text(
        "\n".join(summary_lines),
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return WAITING_CONFIRMATION


async def photos_skip(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """El usuario omitió las fotos."""
    # Reutilizar photos_done sin fotos
    return await photos_done(update, context)


async def confirm_complete(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Confirma y ejecuta el cierre del evento."""
    query = update.callback_query
    await query.answer()

    orchestrator = context.bot_data["orchestrator"]
    evento_id = context.user_data.get("completing_evento_id")
    closure_data = context.user_data.get("closure_data", {})

    result = await orchestrator.complete_event(
        evento_id=evento_id,
        closure_data=closure_data,
    )

    if result.ok:
        await query.edit_message_text(Messages.EVENT_COMPLETED)
    else:
        await query.edit_message_text(f"❌ {result.message}")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_complete(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Cancela el cierre."""
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
    """Retorna el ConversationHandler para terminar/cerrar eventos."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                start_terminar,
                pattern=f"^{CallbackData.TERMINAR_EVENTO}$",
            ),
            # Entry point directo: cuando natural.py muestra la lista de eventos
            # y el usuario presiona un botón terminar_{id}
            CallbackQueryHandler(select_evento, pattern=r"^terminar_\d+$"),
        ],
        states={
            WAITING_SELECT: [
                CallbackQueryHandler(select_evento, pattern=r"^terminar_\d+$"),
            ],
            WAITING_CLOSURE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER,
                    receive_closure,
                ),
            ],
            WAITING_PHOTOS: [
                MessageHandler(filters.PHOTO, receive_photo),
                CallbackQueryHandler(
                    photos_done,
                    pattern=f"^{CallbackData.PHOTOS_DONE}$",
                ),
                CallbackQueryHandler(
                    photos_skip,
                    pattern=f"^{CallbackData.PHOTOS_SKIP}$",
                ),
            ],
            WAITING_CONFIRMATION: [
                CallbackQueryHandler(
                    confirm_complete,
                    pattern=f"^{CallbackData.CONFIRM_YES}$",
                ),
                CallbackQueryHandler(
                    cancel_complete,
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
            CallbackQueryHandler(
                cancel_complete,
                pattern=f"^{CallbackData.CANCEL}$",
            ),
        ],
        conversation_timeout=300,
    )
