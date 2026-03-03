# src/main.py
"""Entry point del sistema — arranca BD, Calendar, LLM, Orchestrator y Bot."""

import logging
import sys

from src.bot.app import create_application
from src.calendar_api.async_wrapper import AsyncGoogleCalendarClient
from src.calendar_api.client import GoogleCalendarClient
from src.config import get_settings, validate_settings
from src.core.logging_config import setup_logging
from src.db.database import DatabaseManager
from src.db.repository import Repository
from src.llm.client import build_llm_chain
from src.llm.parser import LLMParser
from src.orchestrator.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

# Referencia al DatabaseManager para cleanup en post_shutdown
_db_manager: DatabaseManager | None = None


def main() -> None:
    """Inicializa todos los componentes y arranca el bot en modo polling.

    python-telegram-bot v20 maneja su propio event loop con run_polling(),
    por lo que esta función es sincrónica. La inicialización async de la BD
    se hace vía post_init del Application, y el cleanup vía post_shutdown.
    """
    global _db_manager

    # 1. Cargar y validar configuración (fail-fast si falta algo)
    settings = get_settings()
    validate_settings()

    # 2. Configurar logging
    setup_logging(settings.log_level, settings.log_file)
    logger.info("Configuración cargada correctamente")

    # 3. Preparar componentes síncronos
    _db_manager = DatabaseManager(settings.sqlite_db_path)

    sync_calendar = GoogleCalendarClient(
        settings.google_service_account_path,
        settings.google_calendar_id,
    )
    calendar_client = AsyncGoogleCalendarClient(sync_calendar)
    logger.info("Google Calendar inicializado")

    llm_chain = build_llm_chain()
    llm_parser = LLMParser(llm_chain)
    logger.info("LLM Parser inicializado")

    # 4. Crear Application con hooks para init/shutdown async
    app = create_application()

    async def post_init(application) -> None:
        """Hook que corre dentro del event loop de PTB — init async aquí."""
        assert _db_manager is not None
        await _db_manager.connect()
        await _db_manager.initialize()
        logger.info("Base de datos inicializada: %s", settings.sqlite_db_path)

        repository = Repository(_db_manager.db)

        orchestrator = Orchestrator(
            repository=repository,
            calendar_client=calendar_client,
            llm_parser=llm_parser,
            settings=settings,
        )
        application.bot_data["orchestrator"] = orchestrator
        logger.info("Orquestador creado e inyectado")

    async def post_shutdown(application) -> None:
        """Hook de cleanup — cerrar BD."""
        if _db_manager:
            await _db_manager.close()
            logger.info("Sistema finalizado")

    app.post_init = post_init
    app.post_shutdown = post_shutdown

    # 5. Arrancar — run_polling maneja su propio event loop
    logger.info("Bot iniciando en modo polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot detenido por el usuario.")
        sys.exit(0)
    except SystemExit as e:
        # validate_settings() lanza SystemExit con mensaje descriptivo
        print(str(e))
        sys.exit(1)
