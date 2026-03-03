# src/calendar_api/async_wrapper.py
"""Wrapper async para Google Calendar API usando asyncio.to_thread()."""

import asyncio
from datetime import datetime

from src.calendar_api.client import GoogleCalendarClient


class AsyncGoogleCalendarClient:
    """Wrapper async que envuelve GoogleCalendarClient con asyncio.to_thread().

    La API de Google Calendar no es async nativa, por lo que este wrapper
    ejecuta las llamadas en un thread separado para no bloquear el event loop.
    """

    def __init__(self, client: GoogleCalendarClient):
        """Inicializa el wrapper async.

        Args:
            client: Instancia de GoogleCalendarClient síncrono.
        """
        self._client = client

    async def create_event(
        self,
        title: str,
        location: str,
        description: str,
        start_datetime: datetime,
        duration_minutes: int = 60,
        color_id: str = "8",
    ) -> str:
        """Crea un evento en Google Calendar (async).

        Returns:
            ID del evento creado.
        """
        return await asyncio.to_thread(
            self._client.create_event,
            title=title,
            location=location,
            description=description,
            start_datetime=start_datetime,
            duration_minutes=duration_minutes,
            color_id=color_id,
        )

    async def update_event(self, event_id: str, **updates) -> bool:
        """Actualiza campos de un evento existente (async).

        Returns:
            True si la actualización fue exitosa.
        """
        return await asyncio.to_thread(
            self._client.update_event,
            event_id,
            **updates,
        )

    async def delete_event(self, event_id: str) -> bool:
        """Elimina un evento del calendario (async).

        Returns:
            True si la eliminación fue exitosa.
        """
        return await asyncio.to_thread(
            self._client.delete_event,
            event_id,
        )

    async def complete_event(self, event_id: str, closure_description: str) -> bool:
        """Completa un evento: color verde + descripción de cierre (async).

        Returns:
            True si la operación fue exitosa.
        """
        return await asyncio.to_thread(
            self._client.complete_event,
            event_id,
            closure_description,
        )

    async def list_upcoming_events(self, max_results: int = 50) -> list[dict]:
        """Lista eventos futuros del calendario (async).

        Returns:
            Lista de diccionarios con datos de eventos.
        """
        return await asyncio.to_thread(
            self._client.list_upcoming_events,
            max_results,
        )

    async def check_availability(self, start: datetime, end: datetime) -> bool:
        """Verifica si hay conflictos de horario (async).

        Returns:
            True si el horario está disponible.
        """
        return await asyncio.to_thread(
            self._client.check_availability,
            start,
            end,
        )
