# src/core/logging_config.py
"""Configuración de logging estructurado con rotación de archivos."""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_level: str = "DEBUG", log_file: str = "logs/agente.log") -> None:
    """Configura el logging del sistema.

    Args:
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Ruta al archivo de log.
    """
    # Crear directorio de logs si no existe
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Formato consistente
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)-25s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler de archivo con rotación
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # Handler de consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Root logger
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper()))
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Silenciar loggers ruidosos
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
