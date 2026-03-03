# tests/unit/test_config.py
"""Tests para la configuración con Pydantic Settings."""

import os
import pytest
from unittest.mock import patch


class TestSettings:
    """Tests para la clase Settings y funciones asociadas."""

    def setup_method(self):
        """Reset singleton antes de cada test."""
        from src.config import reset_settings

        reset_settings()

    def _make_env(self, **overrides):
        """Genera un dict de variables de entorno mínimas válidas."""
        base = {
            "TELEGRAM_BOT_TOKEN": "test-token-123",
            "ADMIN_TELEGRAM_IDS": "[111,222]",
            "EDITOR_TELEGRAM_IDS": "[333]",
            "GROQ_API_KEY": "gsk_test_key",
            "GOOGLE_CALENDAR_ID": "test@group.calendar.google.com",
        }
        base.update(overrides)
        return base

    @patch.dict(os.environ, clear=True)
    def test_get_settings_with_valid_env(self):
        """Settings se crea correctamente con variables válidas."""
        env = self._make_env()
        with patch.dict(os.environ, env):
            from src.config import get_settings, reset_settings

            reset_settings()
            settings = get_settings()
            assert settings.telegram_bot_token == "test-token-123"
            assert settings.admin_telegram_ids == [111, 222]
            assert settings.editor_telegram_ids == [333]
            assert settings.groq_api_key == "gsk_test_key"

    @patch.dict(os.environ, clear=True)
    def test_settings_defaults(self):
        """Los valores por defecto se aplican correctamente."""
        env = self._make_env()
        with patch.dict(os.environ, env):
            from src.config import get_settings, reset_settings

            reset_settings()
            settings = get_settings()
            assert settings.work_days_weekday_start == "15:00"
            assert settings.work_days_weekday_end == "21:00"
            assert settings.work_days_saturday_start == "08:00"
            assert settings.work_days_saturday_end == "20:00"
            assert settings.timezone == "America/Argentina/Buenos_Aires"
            assert settings.sqlite_db_path == "data/crm.db"
            assert settings.fuzzy_match_threshold == 75
            assert settings.log_level == "DEBUG"
            assert settings.log_file == "logs/agente.log"

    @patch.dict(os.environ, clear=True)
    def test_settings_custom_values(self):
        """Se pueden sobrescribir valores por defecto."""
        env = self._make_env(
            WORK_DAYS_WEEKDAY_START="09:00",
            FUZZY_MATCH_THRESHOLD="80",
            LOG_LEVEL="INFO",
        )
        with patch.dict(os.environ, env):
            from src.config import get_settings, reset_settings

            reset_settings()
            settings = get_settings()
            assert settings.work_days_weekday_start == "09:00"
            assert settings.fuzzy_match_threshold == 80
            assert settings.log_level == "INFO"

    @patch.dict(os.environ, clear=True)
    def test_parse_telegram_ids_from_json_string(self):
        """Los IDs de Telegram se parsean correctamente desde JSON string."""
        env = self._make_env(
            ADMIN_TELEGRAM_IDS="[100,200,300]",
            EDITOR_TELEGRAM_IDS="[]",
        )
        with patch.dict(os.environ, env):
            from src.config import get_settings, reset_settings

            reset_settings()
            settings = get_settings()
            assert settings.admin_telegram_ids == [100, 200, 300]
            assert settings.editor_telegram_ids == []

    @patch.dict(os.environ, clear=True)
    def test_singleton_returns_same_instance(self):
        """get_settings() devuelve siempre la misma instancia."""
        env = self._make_env()
        with patch.dict(os.environ, env):
            from src.config import get_settings, reset_settings

            reset_settings()
            s1 = get_settings()
            s2 = get_settings()
            assert s1 is s2

    @patch.dict(os.environ, clear=True)
    def test_missing_required_field_raises(self):
        """Si falta un campo requerido, Settings no se puede crear."""
        # Sin TELEGRAM_BOT_TOKEN
        env = {
            "GROQ_API_KEY": "gsk_test",
            "GOOGLE_CALENDAR_ID": "test@calendar",
        }
        with patch.dict(os.environ, env):
            from src.config import reset_settings
            from pydantic_settings import BaseSettings

            reset_settings()
            with pytest.raises(Exception):
                # _env_file=None evita que lea el .env del proyecto
                from src.config import Settings as SettingsCls

                class TestSettings(SettingsCls):
                    model_config = {
                        "env_file": None,
                        "env_file_encoding": "utf-8",
                        "case_sensitive": False,
                    }

                TestSettings()

    @patch.dict(os.environ, clear=True)
    def test_validate_settings_fails_on_empty_token(self):
        """validate_settings falla si TELEGRAM_BOT_TOKEN está vacío."""
        env = self._make_env(TELEGRAM_BOT_TOKEN="")
        with patch.dict(os.environ, env):
            from src.config import validate_settings, reset_settings

            reset_settings()
            with pytest.raises(SystemExit):
                validate_settings()

    @patch.dict(os.environ, clear=True)
    def test_validate_settings_fails_on_empty_admin_ids(self):
        """validate_settings falla si no hay admin IDs."""
        env = self._make_env(ADMIN_TELEGRAM_IDS="[]")
        with patch.dict(os.environ, env):
            from src.config import validate_settings, reset_settings

            reset_settings()
            with pytest.raises(SystemExit):
                validate_settings()

    @patch.dict(os.environ, clear=True)
    def test_validate_settings_passes_with_valid_config(self):
        """validate_settings no falla con config válida."""
        env = self._make_env()
        with patch.dict(os.environ, env):
            from src.config import validate_settings, reset_settings

            reset_settings()
            # No debería lanzar excepción
            validate_settings()

    @patch.dict(os.environ, clear=True)
    def test_work_hours_invalid_format_raises(self):
        """Formato de hora inválido (no HH:MM) lanza ValidationError."""
        from pydantic import ValidationError

        env = self._make_env(WORK_DAYS_WEEKDAY_START="abc")
        with patch.dict(os.environ, env):
            from src.config import reset_settings, get_settings

            reset_settings()
            with pytest.raises(ValidationError, match="Formato de hora inválido"):
                get_settings()

    @patch.dict(os.environ, clear=True)
    def test_work_hours_out_of_range_raises(self):
        """Hora fuera de rango (25:00) lanza ValidationError."""
        from pydantic import ValidationError

        env = self._make_env(WORK_DAYS_WEEKDAY_START="25:00")
        with patch.dict(os.environ, env):
            from src.config import reset_settings, get_settings

            reset_settings()
            with pytest.raises(ValidationError, match="Hora fuera de rango"):
                get_settings()

    @patch.dict(os.environ, clear=True)
    def test_work_hours_invalid_minutes_raises(self):
        """Minutos fuera de rango (12:99) lanza ValidationError."""
        from pydantic import ValidationError

        env = self._make_env(WORK_DAYS_SATURDAY_END="12:99")
        with patch.dict(os.environ, env):
            from src.config import reset_settings, get_settings

            reset_settings()
            with pytest.raises(ValidationError, match="Hora fuera de rango"):
                get_settings()

    @patch.dict(os.environ, clear=True)
    def test_work_hours_valid_boundary_values(self):
        """Valores límite válidos (00:00, 23:59) se aceptan."""
        env = self._make_env(
            WORK_DAYS_WEEKDAY_START="00:00",
            WORK_DAYS_WEEKDAY_END="23:59",
        )
        with patch.dict(os.environ, env):
            from src.config import get_settings, reset_settings

            reset_settings()
            settings = get_settings()
            assert settings.work_days_weekday_start == "00:00"
            assert settings.work_days_weekday_end == "23:59"
