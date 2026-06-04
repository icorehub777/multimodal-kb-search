from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOGGER_NAME = "kbsearch_cli"
LOG_FILE_NAME = "kbsearch_cli.log"


def query_log_file_path(log_root: Path) -> Path:
    return log_root.resolve() / LOG_FILE_NAME


def configure_query_cli_logging(log_root: Path) -> logging.Logger:
    log_root.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    log_file_path = query_log_file_path(log_root)
    for handler in logger.handlers:
        if isinstance(handler, TimedRotatingFileHandler) and Path(handler.baseFilename) == log_file_path:
            return logger

    handler = TimedRotatingFileHandler(
        log_file_path,
        when="midnight",
        backupCount=30,
        encoding="utf-8",
        delay=True,
    )
    handler.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
