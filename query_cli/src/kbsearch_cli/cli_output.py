from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from kbsearch_cli.models import QueryRunResult


def format_progress_message(phase: str, fields: Mapping[str, object]) -> str:
    parts = [f"phase={phase}"]
    for key, value in fields.items():
        parts.append(f"{key}={value}")
    return "Query progress: " + " ".join(parts)


def format_query_success_output(
    result: QueryRunResult,
    *,
    run_id: str,
    log_path: Path,
) -> str:
    payload = build_query_success_payload(result, run_id=run_id, log_path=log_path)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_query_success_payload(
    result: QueryRunResult,
    *,
    run_id: str,
    log_path: Path,
) -> dict[str, Any]:
    return {
        "status": "finished_with_errors" if result.download_failures else "finished",
        "run_id": run_id,
        "log_path": log_path.as_posix(),
        "output_dir": result.bundle.path.as_posix(),
        "full_text_count": result.full_text_count,
        "vector_count": result.vector_count,
        "download_count": result.download_count,
        "download_failure_count": result.download_failure_count,
        "download_failures_path": result.bundle.download_failures_path.as_posix(),
        "download_failures": [
            failure.to_dict() for failure in result.download_failures
        ],
    }
