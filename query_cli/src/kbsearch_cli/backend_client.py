from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from kbsearch_cli.errors import ExternalServiceError, QueryCliError
from kbsearch_cli.models import PageSearchResult, VectorFileSearchResult


class SecureBackendClient:
    def __init__(self, base_url: str, timeout_seconds: float | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds if timeout_seconds is not None else (10.0, None)

    def search(
        self,
        query: str,
        image_paths: list[Path],
        limit: int,
        min_score: float | None,
    ) -> list[VectorFileSearchResult]:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("requests is required for secure backend calls.") from exc

        search_url = f"{self._base_url}/search/vector"
        try:
            response = requests.post(
                search_url,
                json={
                    "query": query,
                    "images": [_query_image_payload(path) for path in image_paths],
                    "limit": limit,
                    "min_score": min_score,
                },
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise ExternalServiceError(
                f"Secure backend unreachable ({search_url}): {exc}"
            ) from exc
        if response.status_code >= 400:
            detail = response.text.strip().replace("\n", " ")[:200]
            if detail:
                raise ExternalServiceError(
                    f"Secure backend search failed ({search_url}): HTTP {response.status_code} {detail}"
                )
            raise ExternalServiceError(
                f"Secure backend search failed ({search_url}): HTTP {response.status_code}"
            )
        try:
            payload = response.json()
        except (ValueError, TypeError) as exc:
            raise ExternalServiceError(
                f"Secure backend returned non-JSON response ({search_url})."
            ) from exc
        try:
            return _parse_search_response(payload)
        except (TypeError, ValueError, KeyError) as exc:
            raise ExternalServiceError(
                f"Secure backend returned an invalid response ({search_url}): {exc}"
            ) from exc


def _parse_search_response(payload: Any) -> list[VectorFileSearchResult]:
    if not isinstance(payload, dict):
        raise TypeError("root must be an object")
    results = payload.get("results")
    if not isinstance(results, list):
        raise TypeError("results must be an array")
    return [_vector_file_from_payload(item) for item in results]


def _vector_file_from_payload(payload: dict[str, Any]) -> VectorFileSearchResult:
    if not isinstance(payload, dict):
        raise TypeError("result must be an object")
    required_strings = (
        "google_file_id",
        "source_name",
        "source_location",
        "source_url",
        "google_drive_version",
        "google_drive_modified_time",
    )
    for name in required_strings:
        if not isinstance(payload.get(name), str):
            raise TypeError(f"{name} must be a string")
    if not isinstance(payload.get("score"), (int, float)):
        raise TypeError("score must be a number")
    pages = payload.get("pages")
    if not isinstance(pages, list):
        raise TypeError("pages must be an array")
    for page in pages:
        if not isinstance(page, dict):
            raise TypeError("page must be an object")
        if not isinstance(page.get("page_number"), int) or page["page_number"] < 1:
            raise ValueError("page_number must be a positive integer")
        if not isinstance(page.get("score"), (int, float)):
            raise TypeError("page score must be a number")
    return VectorFileSearchResult(
        google_file_id=payload["google_file_id"],
        source_name=payload["source_name"],
        source_location=payload["source_location"],
        source_url=payload["source_url"],
        google_drive_version=payload["google_drive_version"],
        google_drive_modified_time=payload["google_drive_modified_time"],
        score=float(payload["score"]),
        pages=[
            PageSearchResult(
                page_number=page["page_number"],
                score=float(page["score"]),
            )
            for page in pages
        ],
    )


def _query_image_payload(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise QueryCliError(f"Query image not found: {path}")
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return {
        "filename": path.name,
        "mime_type": mime_type,
        "base64_data": base64.b64encode(path.read_bytes()).decode("ascii"),
    }
