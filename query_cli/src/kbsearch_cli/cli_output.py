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


def format_query_started_event(
    *,
    run_id: str,
    output_dir: Path,
    log_path: Path,
) -> str:
    payload = build_query_started_event_payload(
        run_id=run_id,
        output_dir=output_dir,
        log_path=log_path,
    )
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def build_query_started_event_payload(
    *,
    run_id: str,
    output_dir: Path,
    log_path: Path,
) -> dict[str, str]:
    return {
        "event": "query_started",
        "status": "started",
        "run_id": run_id,
        "output_dir": output_dir.as_posix(),
        "log_path": log_path.as_posix(),
        "monitor": "log",
        "stdout": "final_json_on_success",
    }


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
        "downloaded_files_path": result.bundle.downloaded_files_path.as_posix(),
        "downloaded_files": [
            downloaded_file.to_dict() for downloaded_file in result.downloaded_files
        ],
        "download_failure_count": result.download_failure_count,
        "download_failures_path": result.bundle.download_failures_path.as_posix(),
        "warning_count": result.warning_count,
        "warnings_path": result.bundle.warnings_path.as_posix(),
        "download_failures": [
            failure.to_dict() for failure in result.download_failures
        ],
        "warnings": [warning.to_dict() for warning in result.warnings],
    }
