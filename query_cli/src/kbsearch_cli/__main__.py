from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from kbsearch_cli.cli_output import format_progress_message, format_query_success_output
from kbsearch_cli.config import ConfigError, load_query_cli_config
from kbsearch_cli.errors import QueryCliError
from kbsearch_cli.factories import create_query_orchestrator
from kbsearch_cli.logging_config import (
    configure_query_cli_logging,
    create_query_log_context,
    cleanup_old_query_log_files,
    new_query_run_id,
)
from kbsearch_cli.output import reserve_output_directory
from kbsearch_cli.rendering import DocumentPageRenderer, parse_page_numbers
from kbsearch_cli.startup_probe import probe_startup_environment


ProgressCallback = Callable[[str, dict[str, object]], None]


def _write_terminal(
    message: str,
    *,
    stream,
    logger: logging.Logger | None = None,
) -> None:
    try:
        print(message, file=stream, flush=True)
    except OSError as exc:
        if logger is not None:
            logger.warning(
                "terminal output unavailable stream=%s error=%s message=%s",
                "stderr" if stream is sys.stderr else "stdout",
                exc,
                message,
            )


def _emit_progress(
    phase: str,
    fields: dict[str, object],
    *,
    logger: logging.Logger | None = None,
) -> None:
    _write_terminal(
        format_progress_message(phase, fields),
        stream=sys.stderr,
        logger=logger,
    )


def _run_startup_probe(
    config,
    logger: logging.Logger,
    progress: ProgressCallback,
) -> None:
    progress("startup_probe", {"status": "started"})
    logger.info(
        "startup_probe started secure_backend_base_url=%s oauth_client=%s token_cache=%s "
        "cjk_font_path=%s",
        config.secure_backend_base_url,
        config.google_oauth_client_config,
        config.google_oauth_token_cache,
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
        "oauth_client=%s token_cache=%s cjk_font_path=%s",
        result.secure_backend_base_url,
        result.google_drive_authenticated,
        result.google_oauth_client_config,
        result.google_oauth_token_cache,
        result.cjk_font_path,
    )
    progress(
        "startup_probe",
        {
            "status": "finished",
            "google_drive_authenticated": result.google_drive_authenticated,
        },
    )
    if not result.google_drive_authenticated:
        logger.info(
            "startup_probe note Google OAuth sign-in required; complete browser authorization during query"
        )


def _print_query_failure(
    exc: Exception,
    log_path: Path | None,
    logger: logging.Logger | None,
) -> None:
    message = f"Query failed: {exc}"
    if log_path is not None:
        message = f"{message} log={log_path.resolve()}"
    _write_terminal(message, stream=sys.stderr, logger=logger)


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

    render_parser = subparsers.add_parser("render-pdf-pages")
    render_parser.add_argument("--pdf", required=True)
    render_parser.add_argument("--pages", required=True)
    render_parser.add_argument("--output-dir", required=True)

    args = parser.parse_args(argv)

    if args.command == "render-pdf-pages":
        try:
            pdf_path = Path(args.pdf)
            if not pdf_path.is_file():
                raise QueryCliError(f"PDF file not found: {pdf_path}")
            page_numbers = parse_page_numbers(args.pages)
            output_dir = Path(args.output_dir)
            print(
                "Render PDF pages progress: "
                f"status=started pdf={pdf_path} pages={','.join(map(str, page_numbers))}",
                file=sys.stderr,
            )
            page_paths = DocumentPageRenderer().render_pdf_pages(
                pdf_path,
                output_dir,
                page_numbers,
            )
        except (QueryCliError, RuntimeError, OSError) as exc:
            print(f"Render PDF pages failed: {exc}", file=sys.stderr)
            return 1
        print(
            "Render PDF pages progress: "
            f"status=finished output_dir={output_dir} page_count={len(page_paths)}",
            file=sys.stderr,
        )
        print(
            json.dumps(
                {
                    "status": "finished",
                    "pdf": pdf_path.as_posix(),
                    "output_dir": output_dir.as_posix(),
                    "pages": page_numbers,
                    "page_paths": [path.as_posix() for path in page_paths],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "query":
        logger: logging.Logger | None = None
        log_path: Path | None = None
        run_id = new_query_run_id()

        def progress(phase: str, fields: dict[str, object]) -> None:
            progress_fields: dict[str, object] = {}
            if "status" in fields:
                progress_fields["status"] = fields["status"]
            progress_fields["run_id"] = run_id
            progress_fields.update(
                (key, value)
                for key, value in fields.items()
                if key != "status"
            )
            _emit_progress(
                phase,
                progress_fields,
                logger=logger,
            )

        try:
            config = load_query_cli_config()
            started_at = datetime.now()
            log_context = create_query_log_context(
                config.query_logs_root,
                run_id=run_id,
                timestamp=started_at.strftime("%Y%m%d-%H%M%S-%f"),
            )
            log_path = log_context.log_path
            logger = configure_query_cli_logging(log_context)
            output_dir = Path(args.output_dir)
            try:
                removed_logs = cleanup_old_query_log_files(
                    config.query_logs_root,
                    config.query_log_retention_days,
                    now=started_at,
                )
            except OSError as exc:
                logger.exception(
                    "log_cleanup_failed log_dir=%s retention_days=%s error=%s message=%s",
                    config.query_logs_root,
                    config.query_log_retention_days,
                    exc.__class__.__name__,
                    exc,
                )
                raise
            logger.info(
                "query started output_dir=%s log_retention_days=%s removed_old_logs=%s",
                output_dir,
                config.query_log_retention_days,
                removed_logs,
            )
            progress(
                "query",
                {
                    "status": "started",
                    "output_dir": output_dir,
                    "log": log_path,
                },
            )
            reserve_output_directory(output_dir)
            logger.info("query output directory reserved output_dir=%s", output_dir)
            _run_startup_probe(config, logger, progress)
            result = create_query_orchestrator(config).run(
                output_dir=output_dir,
                vector_query=args.vector_query,
                drive_query=args.drive_query,
                image_paths=[Path(path) for path in args.image],
                limit=args.limit,
                min_score=args.min_score,
                progress=progress,
            )
        except (ConfigError, QueryCliError, RuntimeError) as exc:
            if logger is not None:
                logger.exception(
                    "query failed error=%s message=%s",
                    exc.__class__.__name__,
                    exc,
                )
            progress(
                "query",
                {
                    "status": "failed",
                    "error_type": exc.__class__.__name__,
                    "log": log_path or "",
                },
            )
            _print_query_failure(exc, log_path, logger)
            return 1
        except Exception as exc:
            if logger is not None:
                logger.exception(
                    "query failed error=%s message=%s",
                    exc.__class__.__name__,
                    exc,
                )
            progress(
                "query",
                {
                    "status": "failed",
                    "error_type": exc.__class__.__name__,
                    "log": log_path or "",
                },
            )
            _print_query_failure(exc, log_path, logger)
            return 1
        final_status = "finished_with_errors" if result.download_failures else "finished"
        logger.info(
            "query finished status=%s output_dir=%s download_count=%s download_failure_count=%s",
            final_status,
            result.bundle.path,
            result.download_count,
            result.download_failure_count,
        )
        progress(
            "query",
            {
                "status": final_status,
                "output_dir": result.bundle.path,
                "log": log_path,
            },
        )
        _write_terminal(
            format_query_success_output(
                result,
                run_id=run_id,
                log_path=log_path,
            ),
            stream=sys.stdout,
            logger=logger,
        )
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
