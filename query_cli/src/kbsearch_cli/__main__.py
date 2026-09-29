from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from kbsearch_cli.cli_output import (
    format_progress_message,
    format_query_started_event,
    format_query_success_output,
)
from kbsearch_cli.config import ConfigError, load_query_cli_config
from kbsearch_cli.errors import (
    AuthenticationError,
    ExternalServiceError,
    QueryCliError,
    QueryInputError,
)
from kbsearch_cli.factories import create_query_orchestrator, login_google_drive
from kbsearch_cli.logging_config import (
    configure_query_cli_logging,
    create_query_log_context,
    cleanup_old_query_log_files,
    new_query_run_id,
)
from kbsearch_cli.output import reserve_output_directory
from kbsearch_cli.rendering import DocumentPageRenderer, parse_page_numbers
from kbsearch_cli.startup_probe import probe_startup_environment
from kbsearch_cli.viewer_launcher import run_viewer


ProgressCallback = Callable[[str, dict[str, object]], None]


def _normalize_optional_query(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


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
    *,
    probe_secure_backend: bool,
) -> None:
    progress("startup_probe", {"status": "started", "probe_secure_backend": probe_secure_backend})
    logger.info(
        "startup_probe started secure_backend_base_url=%s cjk_font_path=%s "
        "probe_secure_backend=%s",
        config.secure_backend_base_url,
        config.cjk_font_path,
        probe_secure_backend,
    )
    try:
        result = probe_startup_environment(
            config,
            probe_secure_backend=probe_secure_backend,
        )
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
        "oauth_client=%s cjk_font_path=%s",
        result.secure_backend_base_url,
        result.google_drive_authenticated,
        result.google_oauth_client_config,
        result.cjk_font_path,
    )
    progress(
        "startup_probe",
        {
            "status": "finished",
            "google_drive_authenticated": result.google_drive_authenticated,
        },
    )


def _error_kind(exc: Exception) -> str:
    if isinstance(exc, AuthenticationError):
        return "authentication"
    if isinstance(exc, ExternalServiceError):
        return "external_service"
    if isinstance(exc, (ConfigError, QueryInputError)):
        return "input_or_config"
    return "internal"


def _print_query_failure(
    exc: Exception,
    log_path: Path | None,
    logger: logging.Logger | None,
) -> None:
    message = f"Query failed: error_kind={_error_kind(exc)} message={exc}"
    if log_path is not None:
        message = f"{message} log={log_path.resolve()}"
    _write_terminal(message, stream=sys.stderr, logger=logger)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kbsearch",
        description="KBSearch 的 Google Drive 登入、查詢與結果處理工具。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "login",
        help="以瀏覽器完成 Google Drive OAuth 登入。",
        description="開啟瀏覽器完成 Google Drive OAuth，並安全儲存目前使用者的授權。",
    )

    query_parser = subparsers.add_parser(
        "query",
        help="執行向量或 Google Drive 關鍵字搜尋。",
        description="執行搜尋、下載結果並建立可供 Agent 讀取的產物。",
    )
    query_parser.add_argument(
        "--output-dir", required=True, help="本次新建的搜尋結果目錄；執行前不得存在。"
    )
    query_parser.add_argument("--vector-query", default=None, help="送往 secure_backend 的語意查詢文字。")
    query_parser.add_argument("--drive-query", default=None, help="原樣送往 Google Drive API 的 q 查詢式。")
    query_parser.add_argument("--image", action="append", default=[], help="向量搜尋圖片路徑；可重複指定。")
    query_parser.add_argument("--limit", type=int, default=10, help="每種搜尋的結果筆數上限，預設 10。")
    query_parser.add_argument("--min-score", type=float, default=None, help="向量結果最低分數；省略時不過濾。")

    render_parser = subparsers.add_parser(
        "render-pdf-pages",
        help="將指定 PDF 頁面轉為 PNG。",
        description="將一或多個 PDF 頁面轉為 PNG 並輸出 JSON 結果。",
    )
    render_parser.add_argument("--pdf", required=True, help="來源 PDF 路徑。")
    render_parser.add_argument("--pages", required=True, help="頁碼清單或區間，例如 3,5,8-10。")
    render_parser.add_argument("--output-dir", required=True, help="PNG 輸出目錄。")

    subparsers.add_parser(
        "view-results",
        help="啟動搜尋結果檢視網頁。",
        description="依目前設定啟動搜尋結果檢視網頁。",
    )

    args = parser.parse_args(argv)

    if args.command == "login":
        try:
            login_google_drive(load_query_cli_config())
        except (ConfigError, QueryCliError, RuntimeError) as exc:
            print(
                f"Login failed: error_kind={_error_kind(exc)} message={exc}",
                file=sys.stderr,
            )
            return 1
        print(json.dumps({"status": "finished"}, ensure_ascii=False))
        return 0

    if args.command == "view-results":
        try:
            config = load_query_cli_config()
            return run_viewer(
                tasks_dir=config.tasks_root,
                host="127.0.0.1",
                port=config.viewer_port,
            )
        except (ConfigError, RuntimeError) as exc:
            print(f"View results failed: {exc}", file=sys.stderr)
            return 1

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
        vector_query = _normalize_optional_query(args.vector_query)
        drive_query = _normalize_optional_query(args.drive_query)
        output_dir = Path(args.output_dir)
        image_paths = [Path(path) for path in args.image]

        if vector_query is None and drive_query is None and not args.image:
            input_error = QueryInputError(
                "at least one of --vector-query, --drive-query or --image must be provided"
            )
            _print_query_failure(input_error, None, None)
            return 1
        if output_dir.exists():
            input_error = QueryInputError(f"Output directory already exists: {output_dir}")
            _print_query_failure(input_error, None, None)
            return 1
        if args.limit < 1:
            input_error = QueryInputError("--limit must be a positive integer")
            _print_query_failure(input_error, None, None)
            return 1
        if args.min_score is not None and not math.isfinite(args.min_score):
            input_error = QueryInputError(
                "--min-score must be a finite number between -1 and 1"
            )
            _print_query_failure(input_error, None, None)
            return 1
        for image_path in image_paths:
            if not image_path.is_file():
                input_error = QueryInputError(f"Query image not found: {image_path}")
                _print_query_failure(input_error, None, None)
                return 1

        do_vector_search = vector_query is not None or bool(args.image)
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
            started_at = datetime.now(timezone.utc)
            log_context = create_query_log_context(
                config.query_logs_root,
                run_id=run_id,
                timestamp=started_at.strftime("%Y%m%d-%H%M%S-%f"),
            )
            log_path = log_context.log_path
            logger = configure_query_cli_logging(log_context, config.log_level)
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
            _write_terminal(
                format_query_started_event(
                    run_id=run_id,
                    output_dir=output_dir,
                    log_path=log_path,
                ),
                stream=sys.stderr,
                logger=logger,
            )
            progress(
                "query",
                {
                    "status": "started",
                    "output_dir": output_dir,
                    "log": log_path,
                },
            )
            _run_startup_probe(
                config,
                logger,
                progress,
                probe_secure_backend=do_vector_search,
            )
            reserve_output_directory(output_dir)
            logger.info("query output directory reserved output_dir=%s", output_dir)
            result = create_query_orchestrator(config).run(
                output_dir=output_dir,
                vector_query=vector_query,
                drive_query=drive_query,
                image_paths=image_paths,
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
                    "error_kind": _error_kind(exc),
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
                    "error_kind": _error_kind(exc),
                    "error_type": exc.__class__.__name__,
                    "log": log_path or "",
                },
            )
            _print_query_failure(exc, log_path, logger)
            return 1
        final_status = "finished_with_errors" if result.download_failures else "finished"
        logger.info(
            "query finished status=%s output_dir=%s download_count=%s "
            "download_failure_count=%s warning_count=%s",
            final_status,
            result.bundle.path,
            result.download_count,
            result.download_failure_count,
            result.warning_count,
        )
        progress(
            "query",
            {
                "status": final_status,
                "output_dir": result.bundle.path,
                "log": log_path,
                "warning_count": result.warning_count,
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
