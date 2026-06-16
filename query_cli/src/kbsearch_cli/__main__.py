from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from kbsearch_cli.cli_output import format_progress_message, format_query_success_output
from kbsearch_cli.config import ConfigError, load_query_cli_config
from kbsearch_cli.errors import QueryCliError
from kbsearch_cli.factories import create_query_orchestrator
from kbsearch_cli.logging_config import configure_query_cli_logging, query_log_file_path
from kbsearch_cli.output import reserve_output_directory
from kbsearch_cli.startup_probe import probe_startup_environment


def _emit_progress(phase: str, fields: dict[str, object]) -> None:
    print(format_progress_message(phase, fields), file=sys.stderr)


def _run_startup_probe(config, logger: logging.Logger) -> None:
    _emit_progress("startup_probe", {"status": "started"})
    logger.info(
        "startup_probe started secure_backend_base_url=%s oauth_client=%s token_cache=%s "
        "render_downloaded_files=%s libreoffice_command=%s cjk_font_path=%s",
        config.secure_backend_base_url,
        config.google_oauth_client_config,
        config.google_oauth_token_cache,
        config.render_downloaded_files,
        config.libreoffice_command,
        config.cjk_font_path,
    )
    try:
        result = probe_startup_environment(config)
    except Exception as exc:
        logger.exception(
            "startup_probe failed error=%s message=%s secure_backend_base_url=%s",
            exc.__class__.__name__,
            exc,
            config.secure_backend_base_url,
        )
        raise
    logger.info(
        "startup_probe succeeded secure_backend_base_url=%s google_drive_authenticated=%s "
        "oauth_client=%s token_cache=%s render_downloaded_files=%s "
        "libreoffice_command=%s cjk_font_path=%s",
        result.secure_backend_base_url,
        result.google_drive_authenticated,
        result.google_oauth_client_config,
        result.google_oauth_token_cache,
        result.render_downloaded_files,
        result.libreoffice_command,
        result.cjk_font_path,
    )
    _emit_progress(
        "startup_probe",
        {
            "status": "finished",
            "google_drive_authenticated": result.google_drive_authenticated,
            "render_downloaded_files": result.render_downloaded_files,
        },
    )
    if not result.google_drive_authenticated:
        logger.info(
            "startup_probe note Google OAuth sign-in required; complete browser authorization during query"
        )


def _print_query_failure(exc: Exception, log_path: Path | None) -> None:
    message = f"Query failed: {exc}"
    if log_path is not None:
        message = f"{message} log={log_path.resolve()}"
    print(message, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kbsearch")
    subparsers = parser.add_subparsers(dest="command", required=True)

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("--output-dir", required=True)
    query_parser.add_argument("--vector-query", required=True)
    query_parser.add_argument("--drive-query", required=True)
    query_parser.add_argument("--image", action="append", default=[])
    query_parser.add_argument("--limit", type=int, default=10)
    query_parser.add_argument("--min-score", type=float, default=None)

    args = parser.parse_args(argv)

    if args.command == "query":
        logger: logging.Logger | None = None
        log_path: Path | None = None
        try:
            config = load_query_cli_config()
            log_path = query_log_file_path(config.query_logs_root)
            logger = configure_query_cli_logging(config.query_logs_root)
            output_dir = Path(args.output_dir)
            logger.info("query started output_dir=%s", output_dir)
            _emit_progress("query", {"status": "started", "output_dir": output_dir})
            reserve_output_directory(output_dir)
            logger.info("query output directory reserved output_dir=%s", output_dir)
            _run_startup_probe(config, logger)
            result = create_query_orchestrator(config).run(
                output_dir=output_dir,
                vector_query=args.vector_query,
                drive_query=args.drive_query,
                image_paths=[Path(path) for path in args.image],
                limit=args.limit,
                min_score=args.min_score,
                progress=_emit_progress,
            )
        except (ConfigError, QueryCliError, RuntimeError) as exc:
            if logger is not None:
                logger.exception(
                    "query failed error=%s message=%s",
                    exc.__class__.__name__,
                    exc,
                )
            _print_query_failure(exc, log_path)
            return 1
        except Exception as exc:
            if logger is not None:
                logger.exception(
                    "query failed error=%s message=%s",
                    exc.__class__.__name__,
                    exc,
                )
            _print_query_failure(exc, log_path)
            return 1
        print(format_query_success_output(result))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
