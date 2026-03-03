# src/calendar_api/__init__.py
"""Módulo de integración con Google Calendar API v3."""

from src.calendar_api.async_wrapper import AsyncGoogleCalendarClient
from src.calendar_api.client import GoogleCalendarClient
from src.calendar_api.colors import (
    COMPLETED_COLOR,
    SERVICE_COLOR_MAP,
    get_color_for_service,
)
from src.calendar_api.templates import (
    build_completed_description,
    build_event_description,
    build_event_title,
)

__all__ = [
    "AsyncGoogleCalendarClient",
    "GoogleCalendarClient",
    "COMPLETED_COLOR",
    "SERVICE_COLOR_MAP",
    "get_color_for_service",
    "build_completed_description",
    "build_event_description",
    "build_event_title",
]
