"""Application bootstrap helpers."""

from __future__ import annotations

from dataclasses import dataclass

from services.config_manager import AppConfig, ConfigManager
from services.cursor_manager import CursorManager
from services.enhancement_manager import EnhancementManager
from services.image_pipeline import ImagePipeline
from services.logger import LoggerService
from services.overlay_manager import OverlayManager
from services.startup_manager import StartupManager
from services.uninstall_manager import UninstallManager


@dataclass(slots=True)
class AppContext:
    config_manager: ConfigManager
    logger_service: LoggerService
    config: AppConfig
    cursor_manager: CursorManager
    overlay_manager: OverlayManager
    enhancement_manager: EnhancementManager
    image_pipeline: ImagePipeline
    startup_manager: StartupManager
    uninstall_manager: UninstallManager


def bootstrap_app() -> AppContext:
    config_manager = ConfigManager()
    config = config_manager.load()
    logger_service = LoggerService(config_manager.user_log_dir)
    logger_service.configure()
    logger = logger_service.get_logger(__name__)

    cursor_manager = CursorManager(cache_dir=config_manager.user_data_dir / "builtin_cursors")
    overlay_manager = OverlayManager()
    enhancement_manager = EnhancementManager(cursor_manager=cursor_manager, overlay_manager=overlay_manager, config_provider=lambda: config)
    image_pipeline = ImagePipeline(storage_dir=config_manager.user_data_dir / "custom_cursors", cursor_manager=cursor_manager)
    startup_manager = StartupManager()
    uninstall_manager = UninstallManager()

    startup_desired = bool(config.startup.launch_at_startup)
    startup_actual = startup_manager.is_enabled()
    startup_matches = startup_manager.is_registered_for_current_install() if startup_actual else False
    if startup_desired:
        startup_ok = startup_manager.repair_if_needed(True)
        startup_actual = startup_manager.is_enabled()
        if not startup_ok:
            logger.warning("Startup registration repair failed for the current install")
    elif startup_actual:
        # Trust an existing startup entry over a stale local config flag.
        startup_desired = True
    if startup_desired != bool(config.startup.launch_at_startup):
        config.startup.launch_at_startup = startup_desired
        config_manager.save(config)
    elif startup_actual and not startup_matches:
        repaired = startup_manager.repair_if_needed(True)
        if repaired and not config.startup.launch_at_startup:
            config.startup.launch_at_startup = True
            config_manager.save(config)

    logger.info("Atlas-X Cursor Studio bootstrap complete")
    return AppContext(
        config_manager=config_manager,
        logger_service=logger_service,
        config=config,
        cursor_manager=cursor_manager,
        overlay_manager=overlay_manager,
        enhancement_manager=enhancement_manager,
        image_pipeline=image_pipeline,
        startup_manager=startup_manager,
        uninstall_manager=uninstall_manager,
    )
