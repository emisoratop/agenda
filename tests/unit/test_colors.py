# tests/unit/test_colors.py
"""Tests para el módulo de mapeo de colores de Google Calendar."""

import pytest

from src.calendar_api.colors import (
    COMPLETED_COLOR,
    SERVICE_COLOR_MAP,
    get_color_for_service,
)
from src.db.models import TipoServicio


# ── SERVICE_COLOR_MAP ────────────────────────────────────────────────────────


class TestServiceColorMap:
    """Tests para el diccionario SERVICE_COLOR_MAP."""

    def test_instalacion_is_blueberry(self):
        """Instalación mapea a color 9 (Blueberry/azul)."""
        assert SERVICE_COLOR_MAP[TipoServicio.INSTALACION.value] == "9"

    def test_revision_is_banana(self):
        """Revisión mapea a color 5 (Banana/amarillo)."""
        assert SERVICE_COLOR_MAP[TipoServicio.REVISION.value] == "5"

    def test_mantenimiento_is_tangerine(self):
        """Mantenimiento mapea a color 6 (Tangerine/naranja)."""
        assert SERVICE_COLOR_MAP[TipoServicio.MANTENIMIENTO.value] == "6"

    def test_reparacion_is_tangerine(self):
        """Reparación mapea a color 6 (Tangerine/naranja)."""
        assert SERVICE_COLOR_MAP[TipoServicio.REPARACION.value] == "6"

    def test_presupuesto_is_banana(self):
        """Presupuesto mapea a color 5 (Banana/amarillo)."""
        assert SERVICE_COLOR_MAP[TipoServicio.PRESUPUESTO.value] == "5"

    def test_otro_is_graphite(self):
        """Otro mapea a color 8 (Graphite/gris)."""
        assert SERVICE_COLOR_MAP[TipoServicio.OTRO.value] == "8"

    def test_all_tipo_servicio_have_color(self):
        """Todos los TipoServicio tienen un color asignado."""
        for tipo in TipoServicio:
            assert tipo.value in SERVICE_COLOR_MAP, (
                f"TipoServicio.{tipo.name} no tiene color asignado"
            )

    def test_map_has_exactly_six_entries(self):
        """El mapa tiene exactamente 6 entradas (una por TipoServicio)."""
        assert len(SERVICE_COLOR_MAP) == 6


# ── COMPLETED_COLOR ──────────────────────────────────────────────────────────


class TestCompletedColor:
    """Tests para la constante COMPLETED_COLOR."""

    def test_completed_color_is_sage(self):
        """El color de completado es 2 (Sage/verde)."""
        assert COMPLETED_COLOR == "2"

    def test_completed_color_is_string(self):
        """COMPLETED_COLOR es un string."""
        assert isinstance(COMPLETED_COLOR, str)


# ── get_color_for_service ────────────────────────────────────────────────────


class TestGetColorForService:
    """Tests para la función get_color_for_service."""

    def test_instalacion_returns_blueberry(self):
        """Instalación retorna color 9."""
        assert get_color_for_service("instalacion") == "9"

    def test_revision_returns_banana(self):
        """Revisión retorna color 5."""
        assert get_color_for_service("revision") == "5"

    def test_mantenimiento_returns_tangerine(self):
        """Mantenimiento retorna color 6."""
        assert get_color_for_service("mantenimiento") == "6"

    def test_reparacion_returns_tangerine(self):
        """Reparación retorna color 6."""
        assert get_color_for_service("reparacion") == "6"

    def test_presupuesto_returns_banana(self):
        """Presupuesto retorna color 5."""
        assert get_color_for_service("presupuesto") == "5"

    def test_otro_returns_graphite(self):
        """Otro retorna color 8."""
        assert get_color_for_service("otro") == "8"

    def test_unknown_tipo_returns_default_graphite(self):
        """Un tipo desconocido retorna el default (8, gris)."""
        assert get_color_for_service("inexistente") == "8"

    def test_empty_string_returns_default(self):
        """String vacío retorna el default."""
        assert get_color_for_service("") == "8"

    def test_accepts_tipo_servicio_value(self):
        """Acepta el .value de un TipoServicio directamente."""
        for tipo in TipoServicio:
            result = get_color_for_service(tipo.value)
            assert result in ("5", "6", "8", "9")
