from __future__ import annotations

import argparse
import sys

from kbsearch_importer.config import ConfigError, load_importer_config
from kbsearch_importer.errors import ImporterError
from kbsearch_importer.factories import create_sync_orchestrator
from kbsearch_importer.service_probe import probe_external_services


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kbsearch-importer")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("probe-config")
    subparsers.add_parser("probe-services")
    subparsers.add_parser("sync")

    args = parser.parse_args(argv)

    if args.command == "probe-config":
        try:
            load_importer_config()
        except (ConfigError, RuntimeError) as exc:
            print(f"Importer config probe failed: {exc}", file=sys.stderr)
            return 1
        print("Importer config probe succeeded.")
        return 0

    if args.command == "probe-services":
        try:
            config = load_importer_config()
            result = probe_external_services(config)
        except (ConfigError, ImporterError, RuntimeError) as exc:
            print(f"Importer service probe failed: {exc}", file=sys.stderr)
            return 1
        print(
            "Importer service probe succeeded: "
            f"google_documents={result['google_documents']} "
            f"dashscope_dimension={result['dashscope_dimension']} "
            f"qdrant_documents={result['qdrant_documents']}"
        )
        return 0

    if args.command == "sync":
        try:
            config = load_importer_config()
            summary = create_sync_orchestrator(config).run()
        except (ConfigError, ImporterError, RuntimeError) as exc:
            print(f"Importer sync failed: {exc}", file=sys.stderr)
            return 1
        print(
            "Importer sync finished: "
            f"imported={summary.imported} "
            f"deleted={summary.deleted} "
            f"reimported={summary.reimported} "
            f"skipped={summary.skipped}"
        )
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
