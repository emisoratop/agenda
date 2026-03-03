# src/bot/keyboards.py
"""Generadores de teclados inline para el bot de Telegram."""

from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from src.bot.constants import CallbackData, ITEMS_PER_PAGE, get_service_emoji
from src.db.models import Cliente, Evento


def build_persistent_menu() -> ReplyKeyboardMarkup:
    """Construye el teclado persistente con el botón de Menú.

    Este teclado se muestra siempre en la parte inferior del chat,
    permitiendo al usuario acceder al menú sin necesidad de /start.

    Returns:
        ReplyKeyboardMarkup con el botón "📋 Menú".
    """
    return ReplyKeyboardMarkup(
        [["📋 Menú"]],
        resize_keyboard=True,
        is_persistent=True,
    )


def build_main_menu(role: str) -> InlineKeyboardMarkup:
    """Construye el menú principal según el rol del usuario.

    Args:
        role: 'admin' o 'editor'.

    Returns:
        InlineKeyboardMarkup con los botones disponibles.
    """
    buttons: list[list[InlineKeyboardButton]] = []

    # Crear evento — solo admin
    if role == "admin":
        buttons.append(
            [
                InlineKeyboardButton(
                    "📝 Crear Evento",
                    callback_data=CallbackData.CREAR_EVENTO,
                )
            ]
        )

    # Editar y Ver eventos — ambos roles
    buttons.extend(
        [
            [
                InlineKeyboardButton(
                    "✏️ Editar Evento",
                    callback_data=CallbackData.EDITAR_EVENTO,
                )
            ],
            [
                InlineKeyboardButton(
                    "📋 Ver Eventos",
                    callback_data=CallbackData.VER_EVENTOS,
                )
            ],
        ]
    )

    # Eliminar evento — solo admin
    if role == "admin":
        buttons.append(
            [
                InlineKeyboardButton(
                    "🗑️ Eliminar Evento",
                    callback_data=CallbackData.ELIMINAR_EVENTO,
                )
            ]
        )

    # Terminar evento y Ver contactos — ambos roles
    buttons.extend(
        [
            [
                InlineKeyboardButton(
                    "✅ Terminar Evento",
                    callback_data=CallbackData.TERMINAR_EVENTO,
                )
            ],
            [
                InlineKeyboardButton(
                    "👥 Ver Contactos",
                    callback_data=CallbackData.VER_CONTACTOS,
                )
            ],
        ]
    )

    # Editar contacto — solo admin
    if role == "admin":
        buttons.append(
            [
                InlineKeyboardButton(
                    "✏️ Editar Contacto",
                    callback_data=CallbackData.EDITAR_CONTACTO,
                )
            ]
        )

    return InlineKeyboardMarkup(buttons)


def build_event_list_keyboard(
    events: list[Evento],
    action: str = "event",
    clientes: dict[int, Cliente] | None = None,
) -> InlineKeyboardMarkup:
    """Construye un teclado con una lista de eventos seleccionables.

    Cuando se proporciona el diccionario de clientes, el label muestra
    fecha, hora, nombre del cliente y dirección. Sin clientes, usa el
    formato fallback ``Evento #N``.

    Args:
        events: Lista de eventos a mostrar.
        action: Prefijo de acción para el callback_data.
        clientes: Diccionario ``{cliente_id: Cliente}`` opcional para
            enriquecer los labels con nombre y dirección.

    Returns:
        InlineKeyboardMarkup con botones de selección.
    """
    # Límite de Telegram para texto de botones inline
    _MAX_BUTTON_LEN = 64

    buttons: list[list[InlineKeyboardButton]] = []
    for event in events:
        emoji = get_service_emoji(event.tipo_servicio)

        if clientes and event.cliente_id in clientes:
            cliente = clientes[event.cliente_id]
            fecha = event.fecha_hora.strftime("%d/%m")
            hora = event.hora_formateada
            nombre = cliente.nombre or ""
            direccion = cliente.direccion or ""

            if direccion:
                label = f"{emoji} {fecha} {hora} — {nombre}, {direccion}"
            else:
                label = f"{emoji} {fecha} {hora} — {nombre}"

            # Truncar si excede el límite de Telegram
            if len(label) > _MAX_BUTTON_LEN:
                label = label[: _MAX_BUTTON_LEN - 1] + "…"
        else:
            label = f"{emoji} {event.hora_formateada} — Evento #{event.id}"

        buttons.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"{action}_{event.id}",
                )
            ]
        )
    buttons.append(
        [InlineKeyboardButton("❌ Cancelar", callback_data=CallbackData.CANCEL)]
    )
    return InlineKeyboardMarkup(buttons)


def build_contact_list_keyboard(
    contacts: list[Cliente],
) -> InlineKeyboardMarkup:
    """Construye un teclado con una lista de contactos seleccionables.

    Args:
        contacts: Lista de contactos a mostrar.

    Returns:
        InlineKeyboardMarkup con botones de selección.
    """
    buttons: list[list[InlineKeyboardButton]] = []
    for contact in contacts:
        label = f"👤 {contact.nombre}"
        if contact.telefono:
            label += f" — {contact.telefono}"
        buttons.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"{CallbackData.CONTACT_PREFIX}{contact.id}",
                )
            ]
        )
    buttons.append(
        [InlineKeyboardButton("❌ Cancelar", callback_data=CallbackData.CANCEL)]
    )
    return InlineKeyboardMarkup(buttons)


def build_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Construye un teclado de confirmación (Confirmar / Cancelar).

    Returns:
        InlineKeyboardMarkup con dos botones.
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Confirmar", callback_data=CallbackData.CONFIRM_YES
                ),
                InlineKeyboardButton(
                    "❌ Cancelar", callback_data=CallbackData.CONFIRM_NO
                ),
            ]
        ]
    )


def build_field_selection_keyboard() -> InlineKeyboardMarkup:
    """Construye un teclado para seleccionar qué campo de contacto editar.

    Returns:
        InlineKeyboardMarkup con campos editables.
    """
    buttons = [
        [InlineKeyboardButton("📛 Nombre", callback_data=CallbackData.FIELD_NOMBRE)],
        [
            InlineKeyboardButton(
                "📞 Teléfono", callback_data=CallbackData.FIELD_TELEFONO
            )
        ],
        [
            InlineKeyboardButton(
                "📍 Dirección", callback_data=CallbackData.FIELD_DIRECCION
            )
        ],
        [InlineKeyboardButton("📝 Notas", callback_data=CallbackData.FIELD_NOTAS)],
        [InlineKeyboardButton("❌ Cancelar", callback_data=CallbackData.CANCEL)],
    ]
    return InlineKeyboardMarkup(buttons)


def build_time_slots_keyboard(
    available_slots: list,
    selected: Optional[list[str]] = None,
) -> InlineKeyboardMarkup:
    """Construye un teclado con los horarios disponibles del día.

    Soporta multi-selección (1-3 bloques consecutivos). Los slots ya
    seleccionados se muestran con un check mark.

    Args:
        available_slots: Lista de AvailableSlot del Orquestador.
        selected: Lista de slots ya seleccionados (formato "HH:MM-HH:MM").

    Returns:
        InlineKeyboardMarkup con botones de horarios.
    """
    selected = selected or []
    buttons: list[list[InlineKeyboardButton]] = []

    for slot in available_slots:
        slot_label = f"{slot.start.strftime('%H:%M')} - {slot.end.strftime('%H:%M')}"
        slot_id = f"{slot.start.strftime('%H:%M')}-{slot.end.strftime('%H:%M')}"

        # Marcar slots ya seleccionados
        if slot_id in selected:
            slot_label = f"✅ {slot_label}"

        buttons.append(
            [
                InlineKeyboardButton(
                    slot_label,
                    callback_data=f"{CallbackData.SLOT_PREFIX}{slot_id}",
                )
            ]
        )

    # Botón de confirmar si hay al menos un slot seleccionado
    if selected:
        buttons.append(
            [
                InlineKeyboardButton(
                    "✅ Confirmar selección",
                    callback_data=CallbackData.SLOT_CONFIRM,
                )
            ]
        )

    buttons.append(
        [InlineKeyboardButton("❌ Cancelar", callback_data=CallbackData.CANCEL)]
    )

    return InlineKeyboardMarkup(buttons)


def build_photos_keyboard() -> InlineKeyboardMarkup:
    """Construye un teclado para el paso de fotos en cierre de servicio.

    Returns:
        InlineKeyboardMarkup con opciones de fotos.
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Listo, continuar",
                    callback_data=CallbackData.PHOTOS_DONE,
                )
            ],
            [
                InlineKeyboardButton(
                    "⏭️ Omitir fotos",
                    callback_data=CallbackData.PHOTOS_SKIP,
                )
            ],
        ]
    )


def validate_consecutive_slots(selected_slots: list[str]) -> bool:
    """Verifica que los slots seleccionados sean consecutivos.

    Args:
        selected_slots: Lista de strings "HH:MM-HH:MM".

    Returns:
        True si los slots son consecutivos o hay 0-1 slot.
    """
    if len(selected_slots) <= 1:
        return True

    for i in range(len(selected_slots) - 1):
        current_end = selected_slots[i].split("-")[1]  # "16:00"
        next_start = selected_slots[i + 1].split("-")[0]  # "16:00"
        if current_end != next_start:
            return False
    return True


def paginate_items(
    items: list,
    page: int,
    per_page: int = ITEMS_PER_PAGE,
) -> tuple[list, int]:
    """Pagina una lista de ítems.

    Args:
        items: Lista completa de ítems.
        page: Número de página (0-indexed).
        per_page: Cantidad de ítems por página.

    Returns:
        Tupla (items_de_la_pagina, total_paginas).
    """
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    return items[start : start + per_page], total_pages


def build_pagination_keyboard(
    page: int,
    total_pages: int,
    callback_prefix: str,
) -> Optional[InlineKeyboardMarkup]:
    """Construye teclado con botones de paginación.

    Args:
        page: Página actual (0-indexed).
        total_pages: Total de páginas.
        callback_prefix: Prefijo para callback_data (ej: "ev_page", "cli_page").

    Returns:
        InlineKeyboardMarkup con navegación, o None si hay una sola página.
    """
    if total_pages <= 1:
        return None

    buttons: list[InlineKeyboardButton] = []

    if page > 0:
        buttons.append(
            InlineKeyboardButton(
                "◀ Anterior",
                callback_data=f"{callback_prefix}:{page - 1}",
            )
        )

    buttons.append(
        InlineKeyboardButton(
            f"{page + 1}/{total_pages}",
            callback_data=CallbackData.NOOP,
        )
    )

    if page < total_pages - 1:
        buttons.append(
            InlineKeyboardButton(
                "Siguiente ▶",
                callback_data=f"{callback_prefix}:{page + 1}",
            )
        )

    return InlineKeyboardMarkup([buttons])
