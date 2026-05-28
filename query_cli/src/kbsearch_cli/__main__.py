from __future__ import annotations

import argparse
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from kbsearch_cli.config import ConfigError, load_query_cli_config
from kbsearch_cli.errors import QueryCliError
from kbsearch_cli.factories import create_query_orchestrator


def setup_logging(log_root: Path) -> TimedRotatingFileHandler:
    log_root.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    for existing_handler in list(root_logger.handlers):
        if getattr(existing_handler, "_kbsearch_cli_handler", False):
            root_logger.removeHandler(existing_handler)
            existing_handler.close()
    handler = TimedRotatingFileHandler(
        log_root / "kbsearch_cli.log",
        when="midnight",
        backupCount=30,
        encoding="utf-8",
        delay=True,
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    handler._kbsearch_cli_handler = True
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    return handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kbsearch")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("probe-config")

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("--name", required=True)
    query_parser.add_argument("--vector-query", required=True)
    query_parser.add_argument("--drive-query", required=True)
    query_parser.add_argument("--image", action="append", default=[])
    query_parser.add_argument("--limit", type=int, default=10)
    query_parser.add_argument("--min-score", type=float, default=None)

    args = parser.parse_args(argv)

    if args.command == "probe-config":
        try:
            config = load_query_cli_config()
            setup_logging(config.query_logs_root)
            logging.getLogger(__name__).info("query cli config probe succeeded")
        except (ConfigError, QueryCliError, RuntimeError) as exc:
            print(f"Query CLI config probe failed: {exc}", file=sys.stderr)
            return 1
        print("Query CLI config probe succeeded.")
        return 0

    if args.command == "query":
        try:
            config = load_query_cli_config()
            setup_logging(config.query_logs_root)
            logging.getLogger(__name__).info("query started name=%s", args.name)
            bundle = create_query_orchestrator(config).run(
                query_name=args.name,
                vector_query=args.vector_query,
                drive_query=args.drive_query,
                image_paths=[Path(path) for path in args.image],
                limit=args.limit,
                min_score=args.min_score,
            )
            logging.getLogger(__name__).info(
                "query finished name=%s output=%s",
                args.name,
                bundle.path,
            )
        except (ConfigError, QueryCliError, RuntimeError) as exc:
            logging.getLogger(__name__).exception("query failed")
            print(f"Query failed: {exc}", file=sys.stderr)
            return 1
        print(f"Query finished: output={bundle.path}")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
