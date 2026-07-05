from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

LOGGER_NAME = "importer"
STDOUT_HANDLER_NAME = f"{LOGGER_NAME}.stdout"
RUN_LOG_FILE_PATTERN = "importer-*.log"


def build_run_log_file_path(
    log_dir: Path,
    started_at: datetime | None = None,
    process_id: int | None = None,
) -> Path:
    moment = started_at or datetime.now()
    pid = process_id if process_id is not None else os.getpid()
    return log_dir / f"{moment.strftime('importer-%Y%m%d-%H%M%S-%f')}-p{pid}.log"


def cleanup_old_log_files(
    log_dir: Path,
    retention_days: int,
    *,
    now: datetime | None = None,
) -> int:
    if retention_days <= 0:
        return 0

    log_dir.mkdir(parents=True, exist_ok=True)
    cutoff = (now or datetime.now()) - timedelta(days=retention_days)
    removed = 0
    for path in log_dir.glob(RUN_LOG_FILE_PATTERN):
        if not path.is_file():
            continue
        modified_at = datetime.fromtimestamp(path.stat().st_mtime)
        if modified_at < cutoff:
            path.unlink()
            removed += 1
    return removed


def configure_importer_logging(log_file_path: Path) -> logging.Logger:
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
    current_file_handler: logging.FileHandler | None = None
    for existing_handler in list(logger.handlers):
        if not isinstance(existing_handler, logging.FileHandler):
            continue
        if Path(existing_handler.baseFilename) == resolved_log_path:
            current_file_handler = existing_handler
            continue
        existing_handler.close()
        logger.removeHandler(existing_handler)

    if current_file_handler is not None:
        return logger

    handler = logging.FileHandler(resolved_log_path, encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def _has_stdout_handler(logger: logging.Logger) -> bool:
    return any(handler.get_name() == STDOUT_HANDLER_NAME for handler in logger.handlers)
