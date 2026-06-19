"""Importer entrypoint. Run with: python main.py"""

from __future__ import annotations

import logging
import sys
from datetime import datetime

from app.config import DEFAULT_LOG_DIR, ConfigError, ImporterConfig, load_importer_config
from app.errors import ImporterError
from app.factories import create_sync_orchestrator
from app.logging_config import (
    LOGGER_NAME,
    build_run_log_file_path,
    cleanup_old_log_files,
    configure_importer_logging,
)
from app.startup_probe import probe_startup_environment


def main() -> int:
    logger: logging.Logger | None = None
    try:
        config = load_importer_config()
        started_at = datetime.now()
        log_file = build_run_log_file_path(DEFAULT_LOG_DIR, started_at)
        logger = configure_importer_logging(log_file)
        try:
            removed_logs = cleanup_old_log_files(
                DEFAULT_LOG_DIR,
                config.log_retention_days,
                now=started_at,
            )
        except OSError as exc:
            logger.exception(
                "log_cleanup_failed log_dir=%s retention_days=%s error=%s message=%s",
                DEFAULT_LOG_DIR,
                config.log_retention_days,
                exc.__class__.__name__,
                exc,
            )
            return 1
        logger.info(
            "importer started collection=%s sources=%s log_file=%s "
            "log_retention_days=%s removed_old_logs=%s",
            config.qdrant_collection,
            len(config.google_drive_sources),
            log_file,
            config.log_retention_days,
            removed_logs,
        )
        _run_startup_probe(config, logger)
        summary = create_sync_orchestrator(config).run()
        logger.info(
            "importer finished imported=%s deleted=%s reimported=%s skipped=%s failed=%s",
            summary.imported,
            summary.deleted,
            summary.reimported,
            summary.skipped,
            summary.failed,
        )
        return 1 if summary.failed > 0 else 0
    except (ConfigError, ImporterError, RuntimeError, OSError) as exc:
        if logger is not None:
            logger.exception(
                "importer failed error=%s message=%s",
                exc.__class__.__name__,
                exc,
            )
        else:
            print(f"Importer failed: {exc}", file=sys.stderr)
        return 1


def _run_startup_probe(config: ImporterConfig, logger: logging.Logger) -> None:
    logger.info(
        "startup_probe started dashscope_model=%s dashscope_vector_size=%s "
        "qdrant_collection=%s qdrant_vector_size=%s sources=%s",
        config.dashscope_embedding_model,
        config.dashscope_vector_size,
        config.qdrant_collection,
        config.qdrant_vector_size,
        len(config.google_drive_sources),
    )
    try:
        result = probe_startup_environment(config)
    except Exception as exc:
        logger.exception(
            "startup_probe failed error=%s message=%s dashscope_model=%s qdrant_collection=%s",
            exc.__class__.__name__,
            exc,
            config.dashscope_embedding_model,
            config.qdrant_collection,
        )
        raise
    logger.info(
        "startup_probe succeeded google_documents=%s dashscope_model=%s dashscope_dimension=%s "
        "qdrant_host=%s qdrant_collection=%s qdrant_documents=%s qdrant_vector_size=%s "
        "qdrant_collection_created=%s cjk_font_path=%s",
        result.google_documents,
        result.dashscope_model,
        result.dashscope_dimension,
        result.qdrant_host,
        result.qdrant_collection,
        result.qdrant_documents,
        result.qdrant_vector_size,
        result.qdrant_collection_created,
        result.cjk_font_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
