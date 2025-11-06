"""
Centralized Logging Module

Uses Loguru to provide:
- Colored console output for development
- File rotation and compression for production
- Interception of standard Python logging (FastAPI, uvicorn, SQLAlchemy, etc.)
"""

import logging
import sys
from pathlib import Path

from loguru import logger


# Log level color configuration
LOG_LEVELS = {
    "TRACE": {"color": "<dim><white>"},
    "DEBUG": {"color": "<blue>"},
    "INFO": {"color": "<green>"},
    "SUCCESS": {"color": "<bold><green>"},
    "WARNING": {"color": "<yellow>"},
    "ERROR": {"color": "<red>"},
    "CRITICAL": {"color": "<bold><red>"},
}

# Console log format (colored, detailed)
CONSOLE_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>"
)

# File log format (plain text, detailed)
FILE_LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
)

# Standard Python loggers to intercept
LOGGERS_TO_INTERCEPT = [
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
    "fastapi",
    "asyncio",
    "starlette",
    "httpx",
    "sqlalchemy",
    "alembic",
]


class InterceptHandler(logging.Handler):
    """
    Handler that intercepts standard Python logging and redirects to Loguru
    """

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record by redirecting to Loguru

        Args:
            record: Standard Python logging record
        """
        # Get corresponding Loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller to get correct stack depth
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_back and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "logs/app.log",
    log_rotation: str = "500 MB",
    log_retention: str = "10 days",
    log_compression: str = "zip",
    environment: str = "local",
) -> None:
    """
    Configure unified logging using Loguru

    Args:
        log_level: Minimum log level to capture (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (used in production)
        log_rotation: When to rotate log files (e.g., "500 MB", "1 day")
        log_retention: How long to keep log files (e.g., "10 days", "1 week")
        log_compression: Compression format for rotated logs (e.g., "zip", "gz")
        environment: Application environment (local, test, production)
    """
    # Clear any existing handlers
    logging.root.handlers.clear()
    try:
        logger.remove()
    except ValueError:
        pass  # No handlers to remove

    # Configure custom colors for log levels
    for name, config in LOG_LEVELS.items():
        logger.level(name=name, color=config["color"])

    # Add console handler (always enabled for visibility)
    logger.add(
        sys.stdout,
        level=log_level,
        format=CONSOLE_LOG_FORMAT,
        colorize=True,
        backtrace=True,
        diagnose=True,
        enqueue=False,  # Synchronous for development
    )

    # Add file handler for production mode
    if environment == "production":
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file,
            level=log_level,
            format=FILE_LOG_FORMAT,
            rotation=log_rotation,
            retention=log_retention,
            compression=log_compression,
            colorize=False,
            backtrace=True,
            diagnose=True,
            enqueue=True,  # Asynchronous for production
        )

    # Intercept and redirect standard Python logging to Loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.NOTSET, force=True)

    # Configure specific loggers to intercept
    for logger_name in LOGGERS_TO_INTERCEPT:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers.clear()
        logging_logger.propagate = True


def get_logger(name: str = __name__):
    """
    Get a Loguru logger instance

    Args:
        name: Logger name (usually __name__)

    Returns:
        Loguru logger instance bound to the specified name
    """
    return logger.bind(name=name)
