# src/core/exceptions.py
"""Jerarquía de excepciones de dominio del Agente Calendario."""


class AgenteCalendarioError(Exception):
    """Excepción base del sistema."""

    def __init__(self, message: str, details: str = ""):
        self.message = message
        self.details = details
        super().__init__(message)


# -- Errores de Repositorio --


class DatabaseError(AgenteCalendarioError):
    """Error de base de datos."""

    pass


class ClienteNotFoundError(AgenteCalendarioError):
    """Cliente no encontrado."""

    pass


class EventoNotFoundError(AgenteCalendarioError):
    """Evento no encontrado."""

    pass


class DuplicateClienteError(AgenteCalendarioError):
    """Ya existe un cliente con ese teléfono."""

    pass


# -- Errores de Calendar --


class CalendarError(AgenteCalendarioError):
    """Error de Google Calendar API."""

    pass


class CalendarSyncError(CalendarError):
    """Error de sincronización BD <-> Calendar."""

    pass


# -- Errores de LLM --


class LLMError(AgenteCalendarioError):
    """Error del servicio LLM."""

    pass


class LLMParsingError(LLMError):
    """El LLM devolvió una respuesta no parseable."""

    pass


class LLMUnavailableError(LLMError):
    """Todos los proveedores LLM están caídos."""

    pass


# -- Errores de Negocio --


class ScheduleConflictError(AgenteCalendarioError):
    """Conflicto de horario: ya hay un evento agendado.

    Attributes:
        conflicting_event: Datos del evento existente que genera el conflicto.
        available_slots: Lista de horarios alternativos disponibles
            (cada slot es un dict con 'inicio' y 'fin' como datetime).
    """

    def __init__(
        self,
        message: str,
        details: str = "",
        conflicting_event: dict | None = None,
        available_slots: list[dict] | None = None,
    ):
        super().__init__(message, details)
        self.conflicting_event = conflicting_event
        self.available_slots = available_slots or []


class PermissionDeniedError(AgenteCalendarioError):
    """El usuario no tiene permisos para esta acción."""

    pass


class InvalidDateError(AgenteCalendarioError):
    """Fecha u hora inválida (pasada, fuera de rango, etc.)."""

    pass
