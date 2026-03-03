# tests/unit/test_templates.py
"""Tests para los templates de descripción de eventos de Google Calendar."""

import pytest

from src.calendar_api.templates import (
    build_completed_description,
    build_event_description,
    build_event_title,
)


# ── build_event_title ────────────────────────────────────────────────────────


class TestBuildEventTitle:
    """Tests para build_event_title."""

    def test_format_basic(self):
        """Formato básico: Nombre — Teléfono."""
        result = build_event_title("Juan Pérez", "351-1234567")
        assert result == "Juan Pérez — 351-1234567"

    def test_uses_em_dash(self):
        """Usa em dash (—) como separador, no guión simple."""
        result = build_event_title("Ana", "123")
        assert "—" in result
        assert " — " in result

    def test_preserves_special_characters(self):
        """Preserva caracteres especiales en nombre y teléfono."""
        result = build_event_title("María García", "+5491155551234")
        assert result == "María García — +5491155551234"


# ── build_event_description ──────────────────────────────────────────────────


class TestBuildEventDescription:
    """Tests para build_event_description."""

    def test_contains_tipo_servicio(self):
        """La descripción contiene el tipo de servicio capitalizado."""
        result = build_event_description("instalacion", "Av. Corrientes 1234")
        assert "📋 Tipo: Instalacion" in result

    def test_contains_direccion(self):
        """La descripción contiene la dirección."""
        result = build_event_description("revision", "Balcarce 132")
        assert "📍 Dirección: Balcarce 132" in result

    def test_contains_notas(self):
        """La descripción contiene las notas cuando se proporcionan."""
        result = build_event_description(
            "instalacion", "Calle 1", notas="Poner 3 cámaras"
        )
        assert "📝 Notas: Poner 3 cámaras" in result

    def test_notas_empty_shows_dash(self):
        """Sin notas muestra un guión."""
        result = build_event_description("instalacion", "Calle 1")
        assert "📝 Notas: —" in result

    def test_notas_none_shows_dash(self):
        """Notas vacías muestran un guión."""
        result = build_event_description("instalacion", "Calle 1", notas="")
        assert "📝 Notas: —" in result

    def test_contains_post_servicio_section(self):
        """Incluye sección de post-servicio vacía."""
        result = build_event_description("instalacion", "Calle 1")
        assert "── Post-servicio (completar al terminar) ──" in result

    def test_post_servicio_fields_empty(self):
        """Los campos de post-servicio están vacíos."""
        result = build_event_description("instalacion", "Calle 1")
        assert "✅ Trabajo realizado: \n" in result
        assert "💰 Monto cobrado: \n" in result
        assert "📝 Notas de cierre: \n" in result
        assert "📷 Fotos: \n" in result

    def test_capitalizes_tipo_servicio(self):
        """El tipo de servicio se capitaliza."""
        result = build_event_description("mantenimiento", "Calle 1")
        assert "Mantenimiento" in result
        assert "mantenimiento" not in result.split("Tipo: ")[1].split("\n")[0]


# ── build_completed_description ──────────────────────────────────────────────


class TestBuildCompletedDescription:
    """Tests para build_completed_description."""

    def test_contains_tipo_servicio(self):
        """La descripción completada contiene el tipo de servicio."""
        result = build_completed_description(
            "instalacion", "Calle 1", "Notas", "Se instaló", 45000.0
        )
        assert "📋 Tipo: Instalacion" in result

    def test_contains_direccion(self):
        """La descripción completada contiene la dirección."""
        result = build_completed_description(
            "instalacion", "Balcarce 132", "Notas", "Se instaló", 45000.0
        )
        assert "📍 Dirección: Balcarce 132" in result

    def test_contains_trabajo_realizado(self):
        """Incluye el trabajo realizado."""
        result = build_completed_description(
            "instalacion", "Calle 1", "", "Se instalaron 3 cámaras", 45000.0
        )
        assert "✅ Trabajo realizado: Se instalaron 3 cámaras" in result

    def test_contains_monto_cobrado(self):
        """Incluye el monto cobrado con formato de moneda."""
        result = build_completed_description(
            "instalacion", "Calle 1", "", "Trabajo", 45000.0
        )
        assert "💰 Monto cobrado: $45,000" in result

    def test_monto_zero(self):
        """Monto cero se muestra correctamente."""
        result = build_completed_description(
            "instalacion", "Calle 1", "", "Trabajo", 0.0
        )
        assert "💰 Monto cobrado: $0" in result

    def test_contains_notas_cierre(self):
        """Incluye notas de cierre cuando se proporcionan."""
        result = build_completed_description(
            "instalacion",
            "Calle 1",
            "",
            "Trabajo",
            1000.0,
            notas_cierre="Cliente satisfecho",
        )
        assert "📝 Notas de cierre: Cliente satisfecho" in result

    def test_notas_cierre_empty_shows_dash(self):
        """Sin notas de cierre muestra guión."""
        result = build_completed_description(
            "instalacion", "Calle 1", "", "Trabajo", 1000.0
        )
        assert "📝 Notas de cierre: —" in result

    def test_contains_fotos(self):
        """Incluye las fotos separadas por coma."""
        result = build_completed_description(
            "instalacion",
            "Calle 1",
            "",
            "Trabajo",
            1000.0,
            fotos=["foto1.jpg", "foto2.jpg"],
        )
        assert "📷 Fotos: foto1.jpg, foto2.jpg" in result

    def test_fotos_none_shows_dash(self):
        """Sin fotos muestra guión."""
        result = build_completed_description(
            "instalacion", "Calle 1", "", "Trabajo", 1000.0
        )
        assert "📷 Fotos: —" in result

    def test_fotos_empty_list_shows_dash(self):
        """Lista de fotos vacía muestra guión."""
        result = build_completed_description(
            "instalacion", "Calle 1", "", "Trabajo", 1000.0, fotos=[]
        )
        assert "📷 Fotos: —" in result

    def test_post_servicio_header_without_completar(self):
        """La sección de post-servicio NO dice 'completar al terminar'."""
        result = build_completed_description(
            "instalacion", "Calle 1", "", "Trabajo", 1000.0
        )
        assert "── Post-servicio ──" in result
        assert "completar al terminar" not in result

    def test_notas_originales_empty_shows_dash(self):
        """Notas originales vacías muestran guión."""
        result = build_completed_description(
            "instalacion", "Calle 1", "", "Trabajo", 1000.0
        )
        assert "📝 Notas: —" in result

    def test_full_example(self):
        """Ejemplo completo del spec."""
        result = build_completed_description(
            tipo_servicio="instalacion",
            direccion="Balcarce 132",
            notas="Poner 3 cámaras y cambiar 1 batería de alarma",
            trabajo_realizado="Se instalaron 3 cámaras domo y se cambió batería",
            monto_cobrado=45000.0,
            notas_cierre="Cliente satisfecho, queda pendiente revisión en 3 meses",
            fotos=["foto1.jpg", "foto2.jpg"],
        )
        assert "Instalacion" in result
        assert "Balcarce 132" in result
        assert "Poner 3 cámaras" in result
        assert "Se instalaron 3 cámaras domo" in result
        assert "$45,000" in result
        assert "Cliente satisfecho" in result
        assert "foto1.jpg, foto2.jpg" in result
