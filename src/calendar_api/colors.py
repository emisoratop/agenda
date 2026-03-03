# src/calendar_api/colors.py
"""Mapeo de colores de Google Calendar por tipo de servicio."""

from src.db.models import TipoServicio

# Mapa tipo_servicio → color_id de Google Calendar
SERVICE_COLOR_MAP: dict[str, str] = {
    TipoServicio.INSTALACION.value: "9",  # Blueberry (azul)
    TipoServicio.REVISION.value: "5",  # Banana (amarillo)
    TipoServicio.MANTENIMIENTO.value: "6",  # Tangerine (naranja)
    TipoServicio.REPARACION.value: "6",  # Tangerine (naranja)
    TipoServicio.PRESUPUESTO.value: "5",  # Banana (amarillo)
    TipoServicio.OTRO.value: "8",  # Graphite (gris)
}

# Color para eventos con EstadoEvento.COMPLETADO (aplicado al completar, no por tipo)
COMPLETED_COLOR: str = "2"  # Sage (verde)


def get_color_for_service(tipo: str) -> str:
    """Retorna el color ID de Google Calendar para un tipo de servicio.

    Args:
        tipo: Valor del tipo de servicio (ej: "instalacion").

    Returns:
        Color ID como string. Default: "8" (gris) si el tipo no existe.
    """
    return SERVICE_COLOR_MAP.get(tipo, "8")
