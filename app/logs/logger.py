from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from app.config.settings import Settings


def configure_logger(settings: Settings) -> None:
    """
    Configure production-grade logging.

    Logs:
    - Console output for development visibility.
    - Daily rotating log file for audit/debugging.
    - Error-only log file for faster issue investigation.
    """

    logger.remove()

    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        sys.stdout,
        level=settings.normalized_log_level,
        colorize=True,
        backtrace=False,
        diagnose=False,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
    )

    logger.add(
        log_dir / "goldx_bot_{time:YYYY-MM-DD}.log",
        level=settings.normalized_log_level,
        rotation="00:00",
        retention="30 days",
        compression="zip",
        backtrace=False,
        diagnose=False,
        enqueue=True,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        ),
    )

    logger.add(
        log_dir / "goldx_errors_{time:YYYY-MM-DD}.log",
        level="ERROR",
        rotation="00:00",
        retention="60 days",
        compression="zip",
        backtrace=True,
        diagnose=False,
        enqueue=True,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        ),
    )


def get_logger():
    return logger
