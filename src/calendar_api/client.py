# src/calendar_api/client.py
"""Cliente de Google Calendar API con CRUD de eventos y retry con backoff."""

import logging
import time as time_module
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from googleapiclient.errors import HttpError

from src.calendar_api.auth import build_calendar_service
from src.calendar_api.colors import COMPLETED_COLOR
from src.core.exceptions import CalendarError

logger = logging.getLogger(__name__)

TIMEZONE = "America/Argentina/Buenos_Aires"

# Configuración de retry con backoff exponencial
MAX_RETRIES = 3
BASE_DELAY = 1.0  # segundos
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _retry_with_backoff(func, *args, **kwargs) -> Any:
    """Ejecuta una función con retry y backoff exponencial.

    Reintenta en errores transitorios de red o rate limiting.

    Args:
        func: Función a ejecutar.
        *args: Argumentos posicionales.
        **kwargs: Argumentos keyword.

    Returns:
        Resultado de la función.

    Raises:
        CalendarError: Si se agotan los reintentos.
    """
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except HttpError as e:
            last_exception = e
            status_code = e.resp.status if e.resp else 0
            if status_code not in RETRYABLE_STATUS_CODES:
                raise CalendarError(
                    f"Error de Google Calendar API: {e}",
                    details=f"HTTP {status_code}",
                )
            delay = BASE_DELAY * (2**attempt)
            logger.warning(
                f"Error HTTP {status_code} en intento {attempt + 1}/{MAX_RETRIES}. "
                f"Reintentando en {delay}s..."
            )
            time_module.sleep(delay)
        except Exception as e:
            last_exception = e
            delay = BASE_DELAY * (2**attempt)
            logger.warning(
                f"Error de red en intento {attempt + 1}/{MAX_RETRIES}: {e}. "
                f"Reintentando en {delay}s..."
            )
            time_module.sleep(delay)

    raise CalendarError(
        f"Se agotaron los reintentos ({MAX_RETRIES}) para la operación de Calendar.",
        details=str(last_exception),
    )


class GoogleCalendarClient:
    """Wrapper simplificado de Google Calendar API v3."""

    def __init__(self, service_account_path: str, calendar_id: str):
        """Inicializa el cliente de Google Calendar.

        Args:
            service_account_path: Ruta al archivo JSON de la Service Account.
            calendar_id: ID del calendario de Google.
        """
        self.calendar_id = calendar_id
        self.service = build_calendar_service(service_account_path)

    def create_event(
        self,
        title: str,
        location: str,
        description: str,
        start_datetime: datetime,
        duration_minutes: int = 60,
        color_id: str = "8",
    ) -> str:
        """Crea un evento en Google Calendar.

        Args:
            title: Título del evento (formato "Nombre — Teléfono").
            location: Dirección del servicio.
            description: Descripción formateada del evento.
            start_datetime: Fecha y hora de inicio.
            duration_minutes: Duración en minutos (default: 60).
            color_id: ID del color de Google Calendar (default: "8" gris).

        Returns:
            ID del evento creado en Google Calendar.

        Raises:
            CalendarError: Si falla la creación del evento.
        """
        end_datetime = start_datetime + timedelta(minutes=duration_minutes)

        event_body = {
            "summary": title,
            "location": location,
            "description": description,
            "start": {
                "dateTime": start_datetime.isoformat(),
                "timeZone": TIMEZONE,
            },
            "end": {
                "dateTime": end_datetime.isoformat(),
                "timeZone": TIMEZONE,
            },
            "colorId": color_id,
        }

        event = _retry_with_backoff(
            self.service.events()
            .insert(calendarId=self.calendar_id, body=event_body)
            .execute
        )

        logger.info(f"Evento creado: {event['id']} - {title}")
        return event["id"]

    def update_event(self, event_id: str, **updates) -> bool:
        """Actualiza campos de un evento existente.

        Args:
            event_id: ID del evento en Google Calendar.
            **updates: Campos a actualizar. Soporta:
                - summary, location, description: Strings directos.
                - start_datetime, end_datetime: Objetos datetime.
                - color_id: ID del color.

        Returns:
            True si la actualización fue exitosa.

        Raises:
            CalendarError: Si falla la actualización.
        """
        try:
            event = _retry_with_backoff(
                self.service.events()
                .get(calendarId=self.calendar_id, eventId=event_id)
                .execute
            )

            for key, value in updates.items():
                if key in ("start_datetime", "end_datetime"):
                    dt_key = "start" if "start" in key else "end"
                    event[dt_key] = {
                        "dateTime": value.isoformat(),
                        "timeZone": TIMEZONE,
                    }
                elif key == "color_id":
                    event["colorId"] = value
                else:
                    event[key] = value

            _retry_with_backoff(
                self.service.events()
                .update(
                    calendarId=self.calendar_id,
                    eventId=event_id,
                    body=event,
                )
                .execute
            )

            logger.info(f"Evento actualizado: {event_id}")
            return True

        except CalendarError:
            raise
        except Exception as e:
            logger.error(f"Error actualizando evento {event_id}: {e}")
            raise CalendarError(
                f"Error actualizando evento {event_id}",
                details=str(e),
            )

    def delete_event(self, event_id: str) -> bool:
        """Elimina un evento del calendario.

        Args:
            event_id: ID del evento en Google Calendar.

        Returns:
            True si la eliminación fue exitosa.

        Raises:
            CalendarError: Si falla la eliminación.
        """
        try:
            _retry_with_backoff(
                self.service.events()
                .delete(calendarId=self.calendar_id, eventId=event_id)
                .execute
            )
            logger.info(f"Evento eliminado: {event_id}")
            return True

        except CalendarError:
            raise
        except Exception as e:
            logger.error(f"Error eliminando evento {event_id}: {e}")
            raise CalendarError(
                f"Error eliminando evento {event_id}",
                details=str(e),
            )

    def complete_event(self, event_id: str, closure_description: str) -> bool:
        """Completa un evento: cambia color a verde y actualiza descripción.

        Args:
            event_id: ID del evento en Google Calendar.
            closure_description: Descripción actualizada con datos de cierre.

        Returns:
            True si la operación fue exitosa.

        Raises:
            CalendarError: Si falla la operación.
        """
        return self.update_event(
            event_id,
            description=closure_description,
            color_id=COMPLETED_COLOR,
        )

    def list_upcoming_events(self, max_results: int = 50) -> list[dict]:
        """Lista eventos futuros del calendario.

        Args:
            max_results: Número máximo de eventos a retornar (default: 50).

        Returns:
            Lista de diccionarios con datos de eventos.

        Raises:
            CalendarError: Si falla la consulta.
        """
        try:
            now = datetime.now(ZoneInfo(TIMEZONE)).isoformat()
            events_result = _retry_with_backoff(
                self.service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=now,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute
            )
            return events_result.get("items", [])

        except CalendarError:
            raise
        except Exception as e:
            logger.error(f"Error listando eventos: {e}")
            raise CalendarError(
                "Error listando eventos del calendario",
                details=str(e),
            )

    def check_availability(self, start: datetime, end: datetime) -> bool:
        """Verifica si hay conflictos de horario en un rango.

        Args:
            start: Inicio del rango a verificar.
            end: Fin del rango a verificar.

        Returns:
            True si el horario está disponible (sin conflictos).

        Raises:
            CalendarError: Si falla la consulta.
        """
        try:
            events_result = _retry_with_backoff(
                self.service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=start.isoformat(),
                    timeMax=end.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute
            )
            events = events_result.get("items", [])

            if events:
                logger.info(
                    f"Conflicto de horario detectado: {len(events)} evento(s) "
                    f"entre {start.isoformat()} y {end.isoformat()}"
                )
                return False

            return True

        except CalendarError:
            raise
        except Exception as e:
            logger.error(f"Error verificando disponibilidad: {e}")
            raise CalendarError(
                "Error verificando disponibilidad en el calendario",
                details=str(e),
            )
