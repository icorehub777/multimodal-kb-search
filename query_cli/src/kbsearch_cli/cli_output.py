from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from kbsearch_cli.models import QueryRunResult


def format_progress_message(phase: str, fields: Mapping[str, object]) -> str:
    parts = [f"phase={phase}"]
    for key, value in fields.items():
        parts.append(f"{key}={value}")
    return "Query progress: " + " ".join(parts)


def format_query_success_output(result: QueryRunResult) -> str:
    payload = build_query_success_payload(result)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_query_success_payload(result: QueryRunResult) -> dict[str, Any]:
    return {
        "status": "finished",
        "bundle_name": result.bundle.path.name,
        "full_text_count": result.full_text_count,
        "vector_count": result.vector_count,
        "download_count": result.download_count,
    }
