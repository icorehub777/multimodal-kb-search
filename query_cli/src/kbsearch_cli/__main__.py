from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kbsearch_cli.config import ConfigError, load_query_cli_config
from kbsearch_cli.errors import QueryCliError
from kbsearch_cli.factories import create_query_orchestrator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kbsearch")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("probe-config")

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("--name", required=True)
    query_parser.add_argument("--query", required=True)
    query_parser.add_argument("--image", action="append", default=[])
    query_parser.add_argument("--limit", type=int, default=10)
    query_parser.add_argument("--min-score", type=float, default=None)

    args = parser.parse_args(argv)

    if args.command == "probe-config":
        try:
            load_query_cli_config()
        except (ConfigError, QueryCliError, RuntimeError) as exc:
            print(f"Query CLI config probe failed: {exc}", file=sys.stderr)
            return 1
        print("Query CLI config probe succeeded.")
        return 0

    if args.command == "query":
        try:
            config = load_query_cli_config()
            bundle = create_query_orchestrator(config).run(
                query_name=args.name,
                query=args.query,
                image_paths=[Path(path) for path in args.image],
                limit=args.limit,
                min_score=args.min_score,
            )
        except (ConfigError, QueryCliError, RuntimeError) as exc:
            print(f"Query failed: {exc}", file=sys.stderr)
            return 1
        print(f"Query finished: output={bundle.path}")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
