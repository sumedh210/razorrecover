import os
import sys
from pathlib import Path

from loguru import logger


class LoggingConfig:
    

    DEFAULT_LEVEL = "INFO"
    DEFAULT_LOG_DIR = Path("logs")
    DEFAULT_LOG_FILE = "application.log"

    def __init__(
        self,
        level: str | None = None,
        log_dir: Path | None = None,
        log_file: str | None = None,
    ) -> None:
        self.level = (level or os.getenv("LOG_LEVEL", self.DEFAULT_LEVEL,)).upper()

        self.log_dir = (log_dir or Path(os.getenv("LOG_DIR", str(self.DEFAULT_LOG_DIR),)))

        self.log_file = (log_file or os.getenv("LOG_FILE", self.DEFAULT_LOG_FILE,))


class ApplicationLogger:
    

    VALID_LEVELS = {
        "TRACE",
        "DEBUG",
        "INFO",
        "SUCCESS",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }

    _configured = False

    def __init__(self, config: LoggingConfig | None = None,) -> None:
        self._config = config or LoggingConfig()

    def configure(self) -> None:
        
        if self._configured:
            return

        self._validate_level()

        self._config.log_dir.mkdir(parents=True, exist_ok=True,)

        logger.remove()

        self._add_console_handler()
        self._add_file_handler()

        self._configured = True

        logger.info("Logging configured | level={}", self._config.level,)

    def _add_console_handler(self) -> None:
        
        logger.add(
            sys.stderr,
            level=self._config.level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:"
                "<cyan>{function}</cyan>:"
                "<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
            enqueue=True,
            backtrace=True,
            diagnose=False,
        )

    def _add_file_handler(self) -> None:
        
        log_path = (self._config.log_dir / self._config.log_file)

        logger.add(
            log_path,
            level=self._config.level,
            rotation="10 MB",
            retention="7 days",
            compression="zip",
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=False,
        )

    def _validate_level(self) -> None:
        

        if self._config.level not in self.VALID_LEVELS:
            raise ValueError(
                f"Invalid LOG_LEVEL: "
                f"{self._config.level}"
            )


def configure_logging(
    level: str | None = None,
) -> None:
    

    config = LoggingConfig(
        level=level,
    )

    ApplicationLogger(config=config,).configure()