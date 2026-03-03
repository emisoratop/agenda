# src/calendar_api/auth.py
"""Autenticación con Google Calendar API v3 usando Service Account."""

import logging
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def build_calendar_service(
    service_account_path: str,
) -> Any:
    """Construye el servicio de Google Calendar API.

    Args:
        service_account_path: Ruta al archivo JSON de la Service Account.

    Returns:
        Recurso de servicio de Google Calendar API v3.

    Raises:
        FileNotFoundError: Si no se encuentra el archivo de credenciales.
        ValueError: Si las credenciales son inválidas.
    """
    credentials = service_account.Credentials.from_service_account_file(
        service_account_path, scopes=SCOPES
    )
    service = build("calendar", "v3", credentials=credentials)
    logger.info("Servicio de Google Calendar construido exitosamente.")
    return service


def verify_calendar_access(service: Any, calendar_id: str) -> bool:
    """Verifica conectividad con el calendario al arrancar.

    Args:
        service: Servicio de Google Calendar API.
        calendar_id: ID del calendario a verificar.

    Returns:
        True si el acceso es exitoso.

    Raises:
        CalendarError: Si no se puede acceder al calendario.
    """
    try:
        service.calendarList().get(calendarId=calendar_id).execute()
        logger.info(f"Acceso verificado al calendario: {calendar_id}")
        return True
    except Exception as e:
        logger.error(f"Error verificando acceso al calendario {calendar_id}: {e}")
        raise
