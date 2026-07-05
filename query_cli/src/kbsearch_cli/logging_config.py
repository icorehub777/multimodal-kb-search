from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

LOGGER_NAME = "kbsearch_cli"
QUERY_RUN_LOG_PATTERN = "kbsearch-*.log"


@dataclass(frozen=True)
class QueryLogContext:
    run_id: str
    log_path: Path


def new_query_run_id() -> str:
    return uuid4().hex[:8]


def create_query_log_context(
    log_root: Path,
    *,
    run_id: str,
    timestamp: str | None = None,
) -> QueryLogContext:
    resolved_timestamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return QueryLogContext(
        run_id=run_id,
        log_path=log_root.resolve() / f"kbsearch-{resolved_timestamp}-{run_id}.log",
    )


def cleanup_old_query_log_files(
    log_root: Path,
    retention_days: int,
    *,
    now: datetime | None = None,
) -> int:
    if retention_days <= 0:
        return 0

    log_root.mkdir(parents=True, exist_ok=True)
    cutoff = (now or datetime.now()) - timedelta(days=retention_days)
    removed = 0
    for path in log_root.glob(QUERY_RUN_LOG_PATTERN):
        if not path.is_file():
            continue
        modified_at = datetime.fromtimestamp(path.stat().st_mtime)
        if modified_at < cutoff:
            path.unlink()
            removed += 1
    return removed


def configure_query_cli_logging(context: QueryLogContext) -> logging.Logger:
    context.log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter(
        f"%(asctime)s %(levelname)s %(name)s run_id={context.run_id} %(message)s"
    )

    for existing_handler in list(logger.handlers):
        logger.removeHandler(existing_handler)
        existing_handler.close()

    handler = logging.FileHandler(
        context.log_path,
        encoding="utf-8",
        delay=True,
    )
    handler.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
