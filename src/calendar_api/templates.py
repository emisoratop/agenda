# src/calendar_api/templates.py
"""Templates de título, ubicación y descripción para eventos de Google Calendar."""


def build_event_title(nombre: str, telefono: str) -> str:
    """Construye el título del evento para Google Calendar.

    Args:
        nombre: Nombre del cliente.
        telefono: Teléfono del cliente.

    Returns:
        Título con formato "Nombre — Teléfono".
    """
    return f"{nombre} — {telefono}"


def build_event_description(
    tipo_servicio: str,
    direccion: str,
    notas: str = "",
) -> str:
    """Construye la descripción formateada para Google Calendar.

    Incluye sección de post-servicio vacía para completar después.

    Args:
        tipo_servicio: Tipo de servicio (ej: "instalacion").
        direccion: Dirección del servicio.
        notas: Notas adicionales.

    Returns:
        Descripción formateada con sección de cierre vacía.
    """
    return (
        f"📋 Tipo: {tipo_servicio.capitalize()}\n"
        f"📍 Dirección: {direccion}\n"
        f"📝 Notas: {notas or '—'}\n"
        f"\n"
        f"── Post-servicio (completar al terminar) ──\n"
        f"✅ Trabajo realizado: \n"
        f"💰 Monto cobrado: \n"
        f"📝 Notas de cierre: \n"
        f"📷 Fotos: \n"
    )


def build_completed_description(
    tipo_servicio: str,
    direccion: str,
    notas: str,
    trabajo_realizado: str,
    monto_cobrado: float,
    notas_cierre: str = "",
    fotos: list[str] | None = None,
) -> str:
    """Construye la descripción actualizada al completar un servicio.

    Args:
        tipo_servicio: Tipo de servicio (ej: "instalacion").
        direccion: Dirección del servicio.
        notas: Notas originales del evento.
        trabajo_realizado: Descripción del trabajo realizado.
        monto_cobrado: Monto cobrado al cliente.
        notas_cierre: Notas adicionales de cierre.
        fotos: Lista de nombres de archivos de fotos.

    Returns:
        Descripción formateada con sección de cierre completada.
    """
    fotos_text = ", ".join(fotos) if fotos else "—"
    return (
        f"📋 Tipo: {tipo_servicio.capitalize()}\n"
        f"📍 Dirección: {direccion}\n"
        f"📝 Notas: {notas or '—'}\n"
        f"\n"
        f"── Post-servicio ──\n"
        f"✅ Trabajo realizado: {trabajo_realizado}\n"
        f"💰 Monto cobrado: ${monto_cobrado:,.0f}\n"
        f"📝 Notas de cierre: {notas_cierre or '—'}\n"
        f"📷 Fotos: {fotos_text}\n"
    )
