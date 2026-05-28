from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from kbsearch_cli.errors import ExternalServiceError
from kbsearch_cli.models import PageSearchResult, VectorFileSearchResult


class SecureBackendClient:
    def __init__(self, base_url: str, timeout_seconds: float = 60) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

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

        response = requests.post(
            f"{self._base_url}/search/vector",
            json={
                "query": query,
                "images": [_query_image_payload(path) for path in image_paths],
                "limit": limit,
                "min_score": min_score,
            },
            timeout=self._timeout_seconds,
        )
        if response.status_code >= 400:
            raise ExternalServiceError(f"Secure backend search failed: HTTP {response.status_code}")
        payload = response.json()
        return [_vector_file_from_payload(item) for item in payload.get("results", [])]


def _vector_file_from_payload(payload: dict[str, Any]) -> VectorFileSearchResult:
    return VectorFileSearchResult(
        google_file_id=str(payload.get("google_file_id", "")),
        source_name=str(payload.get("source_name", "")),
        source_location=str(payload.get("source_location", "")),
        source_url=str(payload.get("source_url", "")),
        google_drive_version=str(payload.get("google_drive_version", "")),
        google_drive_modified_time=str(payload.get("google_drive_modified_time", "")),
        score=float(payload.get("score", 0)),
        pages=[
            PageSearchResult(
                page_number=int(page.get("page_number", 0)),
                score=float(page.get("score", 0)),
            )
            for page in payload.get("pages", [])
        ],
    )


def _query_image_payload(path: Path) -> dict[str, str]:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return {
        "filename": path.name,
        "mime_type": mime_type,
        "base64_data": base64.b64encode(path.read_bytes()).decode("ascii"),
    }
