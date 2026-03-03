# src/bot/handlers/ver_eventos.py
"""Handler para ver la lista de eventos pendientes."""

import logging

from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from src.bot.constants import CallbackData, Messages
from src.bot.formatters import format_events_list, split_message
from src.bot.keyboards import build_pagination_keyboard, paginate_items
from src.bot.middleware import require_authorized
from src.db.models import Cliente

logger = logging.getLogger(__name__)


@require_authorized
async def ver_eventos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra la lista de eventos pendientes (acción inmediata, sin estados)."""
    query = update.callback_query
    await query.answer()

    orchestrator = context.bot_data["orchestrator"]
    eventos = await orchestrator.repo.list_eventos_pendientes()

    if not eventos:
        await query.edit_message_text(Messages.NO_PENDING_EVENTS)
        return

    # Obtener nombres de clientes para el formato
    clientes_dict = await _build_clientes_dict(orchestrator, eventos)

    # Paginar
    page = 0
    page_items, total_pages = paginate_items(eventos, page)
    text = format_events_list(page_items, clientes_dict)
    keyboard = build_pagination_keyboard(page, total_pages, "ev_page")

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


async def handle_eventos_pagination(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Maneja clicks en botones de paginación de eventos."""
    query = update.callback_query
    await query.answer()

    _, page_str = query.data.rsplit(":", 1)
    page = int(page_str)

    orchestrator = context.bot_data["orchestrator"]
    eventos = await orchestrator.repo.list_eventos_pendientes()

    if not eventos:
        await query.edit_message_text(Messages.NO_PENDING_EVENTS)
        return

    clientes_dict = await _build_clientes_dict(orchestrator, eventos)
    page_items, total_pages = paginate_items(eventos, page)
    text = format_events_list(page_items, clientes_dict)
    keyboard = build_pagination_keyboard(page, total_pages, "ev_page")

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


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


def get_ver_eventos_handlers() -> list:
    """Retorna los handlers para ver eventos.

    Returns:
        Lista de handlers para registrar en la Application.
    """
    return [
        CallbackQueryHandler(ver_eventos, pattern=f"^{CallbackData.VER_EVENTOS}$"),
        CallbackQueryHandler(handle_eventos_pagination, pattern=r"^ev_page:\d+$"),
    ]
