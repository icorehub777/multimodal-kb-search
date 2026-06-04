from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOGGER_NAME = "secure_backend"
STDOUT_HANDLER_NAME = f"{LOGGER_NAME}.stdout"


def configure_backend_logging(log_file_path: Path) -> logging.Logger:
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    if not _has_stdout_handler(logger):
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.set_name(STDOUT_HANDLER_NAME)
        stdout_handler.setLevel(logging.INFO)
        stdout_handler.setFormatter(formatter)
        logger.addHandler(stdout_handler)

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
    )
    handler.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def _has_stdout_handler(logger: logging.Logger) -> bool:
    return any(handler.get_name() == STDOUT_HANDLER_NAME for handler in logger.handlers)
