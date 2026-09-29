from __future__ import annotations

import logging
import sys
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOGGER_NAME = "secure_backend"
STDOUT_HANDLER_NAME = f"{LOGGER_NAME}.stdout"


def configure_backend_logging(log_file_path: Path, log_level: str = "INFO") -> logging.Logger:
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    level = getattr(logging, log_level)
    logger.setLevel(level)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    formatter.converter = time.gmtime

    if not _has_stdout_handler(logger):
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.set_name(STDOUT_HANDLER_NAME)
        logger.addHandler(stdout_handler)
    for existing_handler in logger.handlers:
        existing_handler.setLevel(level)
        existing_handler.setFormatter(formatter)

    resolved_log_path = log_file_path.resolve()
    for handler in logger.handlers:
        if isinstance(handler, TimedRotatingFileHandler) and Path(handler.baseFilename) == resolved_log_path:
            return logger

    handler = TimedRotatingFileHandler(
        resolved_log_path,
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8",
        utc=True,
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def _has_stdout_handler(logger: logging.Logger) -> bool:
    return any(handler.get_name() == STDOUT_HANDLER_NAME for handler in logger.handlers)
