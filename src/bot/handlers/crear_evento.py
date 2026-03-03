# src/bot/handlers/crear_evento.py
"""ConversationHandler para la creación de eventos."""

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
from src.bot.formatters import format_event_confirmation
from src.bot.keyboards import (
    build_confirmation_keyboard,
    build_time_slots_keyboard,
    validate_consecutive_slots,
)
from src.bot.middleware import require_role
from src.core.result import ResultStatus
from src.bot.handlers.start import MENU_BUTTON_FILTER, menu_fallback

logger = logging.getLogger(__name__)

# Estados locales (aliases para legibilidad)
WAITING_DESCRIPTION = States.CREAR_DESCRIPTION
WAITING_DATE = States.CREAR_DATE
WAITING_TIME_SLOT = States.CREAR_TIME_SLOT
WAITING_CONFIRMATION = States.CREAR_CONFIRMATION


# ── Lógica compartida ─────────────────────────────────────────────────────────


async def _process_description(
    text: str,
    context: ContextTypes.DEFAULT_TYPE,
    reply_func,
) -> int:
    """Lógica compartida para procesar una descripción de evento.

    Se usa tanto desde receive_description (texto directo) como desde
    start_crear (texto pre-cargado por el handler natural).

    Args:
        text: Texto con la descripción del evento.
        context: Contexto de la conversación.
        reply_func: Función para enviar la respuesta (reply_text o edit_message_text).
    """
    orchestrator = context.bot_data["orchestrator"]
    context.user_data["original_text"] = text

    result = await orchestrator.create_event_from_text(
        text=text,
        user_id=0,  # No se usa en create_event_from_text actualmente
    )

    if result.ok:
        # Todo completo → resumen y confirmación
        context.user_data["pending_event"] = result.data
        confirmation = format_event_confirmation(result.data)
        keyboard = build_confirmation_keyboard()
        await reply_func(
            confirmation,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        return WAITING_CONFIRMATION

    if result.needs_input:
        slots = result.data.get("available_slots") if result.data else None
        if slots:
            # Tiene fecha, falta hora → mostrar botones de horarios disponibles
            context.user_data["partial_result"] = result
            context.user_data["selected_slots"] = []
            keyboard = build_time_slots_keyboard(slots)
            await reply_func(
                result.question or Messages.ASK_TIME_SLOT,
                reply_markup=keyboard,
            )
            return WAITING_TIME_SLOT
        else:
            # Falta fecha u otros datos → preguntar
            context.user_data["partial_result"] = result
            await reply_func(result.question or Messages.ASK_DATE)
            question = result.question or ""
            return WAITING_DATE if "fecha" in question.lower() else WAITING_DESCRIPTION

    if result.status == ResultStatus.CONFLICT:
        slots = result.data.get("available_slots") if result.data else None
        if slots:
            context.user_data["partial_result"] = result
            context.user_data["selected_slots"] = []
            keyboard = build_time_slots_keyboard(slots)
            await reply_func(
                f"⚠️ {result.message}",
                reply_markup=keyboard,
            )
            return WAITING_TIME_SLOT
        else:
            context.user_data["partial_result"] = result
            await reply_func(f"⚠️ {result.message}")
            return WAITING_DATE

    # Error
    await reply_func(f"❌ Error: {result.message}")
    return ConversationHandler.END


# ── Handlers ──────────────────────────────────────────────────────────────────


@require_role("admin")
async def start_crear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de creación de evento.

    Si hay texto pre-cargado en user_data['natural_create_text'] (proveniente
    del handler natural), lo procesa directamente sin pedir descripción.
    """
    query = update.callback_query
    await query.answer()

    # Guardar chat_id para timeout handler
    context.user_data["chat_id"] = update.effective_chat.id

    # ¿Viene con texto pre-cargado desde el handler natural?
    natural_text = context.user_data.pop("natural_create_text", None)
    if natural_text:
        # Procesar directamente como si el usuario hubiera escrito la descripción
        return await _process_description(
            text=natural_text,
            context=context,
            reply_func=query.edit_message_text,
        )

    await query.edit_message_text(
        Messages.DESCRIBE_EVENT,
        parse_mode="Markdown",
    )
    return WAITING_DESCRIPTION


async def receive_description(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Recibe la descripción en lenguaje natural y la parsea."""
    context.user_data["original_text"] = update.message.text

    return await _process_description(
        text=update.message.text,
        context=context,
        reply_func=update.message.reply_text,
    )


async def receive_date(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Recibe la fecha y re-procesa para obtener horarios disponibles."""
    orchestrator = context.bot_data["orchestrator"]
    original = context.user_data.get("original_text", "")
    combined = f"{original} {update.message.text}"

    result = await orchestrator.create_event_from_text(
        text=combined,
        user_id=update.effective_user.id,
    )

    if result.ok:
        context.user_data["pending_event"] = result.data
        confirmation = format_event_confirmation(result.data)
        keyboard = build_confirmation_keyboard()
        await update.message.reply_text(
            confirmation,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        return WAITING_CONFIRMATION

    if result.needs_input:
        slots = result.data.get("available_slots") if result.data else None
        if slots:
            context.user_data["partial_result"] = result
            context.user_data["selected_slots"] = []
            keyboard = build_time_slots_keyboard(slots)
            await update.message.reply_text(
                result.question or Messages.ASK_TIME_SLOT,
                reply_markup=keyboard,
            )
            return WAITING_TIME_SLOT
        else:
            await update.message.reply_text(Messages.DATE_NOT_UNDERSTOOD)
            return WAITING_DATE

    # Error o conflicto → volver al inicio
    if result.message:
        await update.message.reply_text(f"❌ {result.message}")
    return WAITING_DESCRIPTION


async def receive_time_slot(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Recibe selección de horario por botón inline."""
    query = update.callback_query
    await query.answer()

    slot_data = query.data.replace(CallbackData.SLOT_PREFIX, "")

    if slot_data == "confirm":
        # El usuario confirmó su selección de slots
        selected = context.user_data.get("selected_slots", [])
        if not selected:
            await query.edit_message_text("Seleccioná al menos un horario.")
            return WAITING_TIME_SLOT

        orchestrator = context.bot_data["orchestrator"]

        # Obtener el ParsedEvent del partial_result (contiene la fecha ya parseada)
        partial = context.user_data.get("partial_result")
        if not partial or not partial.data:
            logger.warning("receive_time_slot: no hay partial_result con datos")
            await query.edit_message_text("Sesión expirada. Iniciá de nuevo.")
            return ConversationHandler.END

        parsed = partial.data.get("parsed")
        if not parsed:
            logger.warning("receive_time_slot: partial_result no tiene parsed")
            await query.edit_message_text("Sesión expirada. Iniciá de nuevo.")
            return ConversationHandler.END

        # Calcular hora de inicio y duración desde los slots seleccionados
        start_time = selected[0].split("-")[0]  # "15:00"
        duration = len(selected) * 60

        # Usar el nuevo método que no re-parsea con el LLM
        result = await orchestrator.confirm_slot_selection(
            parsed=parsed,
            selected_time=start_time,
            duration_minutes=duration,
            user_id=update.effective_user.id,
        )

        logger.debug(
            "receive_time_slot confirm: status=%s, message=%s",
            result.status,
            result.message,
        )

        if result.ok:
            context.user_data["pending_event"] = result.data
            confirmation = format_event_confirmation(result.data)
            keyboard = build_confirmation_keyboard()
            await query.edit_message_text(
                confirmation,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            return WAITING_CONFIRMATION

        if result.needs_input:
            slots = result.data.get("available_slots") if result.data else None
            if slots:
                context.user_data["partial_result"] = result
                context.user_data["selected_slots"] = []
                keyboard = build_time_slots_keyboard(slots)
                await query.edit_message_text(
                    result.question or Messages.ASK_TIME_SLOT,
                    reply_markup=keyboard,
                )
                return WAITING_TIME_SLOT
            await query.edit_message_text(
                result.question or Messages.ASK_DATE,
            )
            return WAITING_DATE

        if result.status == ResultStatus.CONFLICT:
            slots = result.data.get("available_slots") if result.data else None
            if slots:
                context.user_data["partial_result"] = result
                context.user_data["selected_slots"] = []
                keyboard = build_time_slots_keyboard(slots)
                await query.edit_message_text(
                    f"⚠️ {result.message}",
                    reply_markup=keyboard,
                )
                return WAITING_TIME_SLOT
            await query.edit_message_text(f"⚠️ {result.message}")
            return WAITING_DATE

        # Error genuino
        await query.edit_message_text(f"❌ {result.message or 'Error inesperado'}")
        return ConversationHandler.END

    # Acumular slots seleccionados (máximo 3 consecutivos)
    selected = context.user_data.get("selected_slots", [])

    if slot_data in selected:
        # Deseleccionar
        selected.remove(slot_data)
    else:
        # Agregar y validar consecutividad
        test_selection = selected + [slot_data]
        test_selection.sort()  # Ordenar por hora para validar
        if len(test_selection) > 3:
            await query.answer("Máximo 3 bloques horarios.", show_alert=True)
            return WAITING_TIME_SLOT
        if not validate_consecutive_slots(test_selection):
            # No consecutivo → resetear y empezar con este slot
            selected = [slot_data]
        else:
            selected = test_selection

    context.user_data["selected_slots"] = selected

    # Re-mostrar keyboard con slots marcados
    partial = context.user_data.get("partial_result")
    slots = partial.data.get("available_slots") if partial and partial.data else []
    keyboard = build_time_slots_keyboard(slots, selected)
    await query.edit_message_text(
        Messages.SLOT_MULTI_SELECT if selected else Messages.ASK_TIME_SLOT,
        reply_markup=keyboard,
    )
    return WAITING_TIME_SLOT


async def confirm_event(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """El usuario confirmó la creación del evento → guardar en BD + Calendar."""
    query = update.callback_query
    await query.answer()

    orchestrator = context.bot_data["orchestrator"]
    pending = context.user_data.get("pending_event", {})

    save_result = await orchestrator.save_confirmed_event(
        evento=pending.get("evento"),
        cliente=pending.get("cliente"),
        parsed=pending.get("parsed"),
    )

    if save_result.ok:
        await query.edit_message_text(
            Messages.EVENT_CREATED,
            parse_mode="Markdown",
        )
    else:
        await query.edit_message_text(f"❌ {save_result.message}")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_event(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """El usuario canceló la creación del evento."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(Messages.CREATION_CANCELLED)
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
    """Handler de timeout para conversaciones abandonadas.

    NOTA: En python-telegram-bot v20+, cuando se dispara conversation_timeout,
    update puede ser None. Se usa context.bot.send_message() directamente.
    """
    chat_id = context.user_data.get("chat_id")
    if chat_id:
        await context.bot.send_message(
            chat_id=chat_id,
            text=Messages.CONVERSATION_TIMEOUT,
        )
    context.user_data.clear()
    return ConversationHandler.END


def get_conversation_handler() -> ConversationHandler:
    """Retorna el ConversationHandler para crear eventos."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_crear, pattern=f"^{CallbackData.CREAR_EVENTO}$"),
        ],
        states={
            WAITING_DESCRIPTION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER,
                    receive_description,
                ),
            ],
            WAITING_DATE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER,
                    receive_date,
                ),
            ],
            WAITING_TIME_SLOT: [
                CallbackQueryHandler(
                    receive_time_slot,
                    pattern=f"^{CallbackData.SLOT_PREFIX}",
                ),
            ],
            WAITING_CONFIRMATION: [
                CallbackQueryHandler(
                    confirm_event,
                    pattern=f"^{CallbackData.CONFIRM_YES}$",
                ),
                CallbackQueryHandler(
                    cancel_event,
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
            CallbackQueryHandler(cancel_event, pattern=f"^{CallbackData.CANCEL}$"),
        ],
        conversation_timeout=300,
    )
