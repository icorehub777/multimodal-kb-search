from __future__ import annotations

import argparse
import sys

from kbsearch_secure_backend.config import ConfigError, load_backend_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kbsearch-secure-backend")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("probe-config")

    args = parser.parse_args(argv)
    if args.command == "probe-config":
        try:
            load_backend_config()
        except (ConfigError, RuntimeError) as exc:
            print(f"Secure backend config probe failed: {exc}", file=sys.stderr)
            return 1
        print("Secure backend config probe succeeded.")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
