from __future__ import annotations

import math
from typing import Any

from kbsearch_backend.errors import ExternalServiceError
from kbsearch_backend.models import PageSearchResult, VectorFileSearchResult


class QdrantSearchAdapter:
    def __init__(self, client: Any, collection: str) -> None:
        self._client = client
        self._collection = collection

    def search_pages(
        self,
        vector: list[float],
        limit: int,
        min_score: float | None = None,
    ) -> list[VectorFileSearchResult]:
        records = self._search(vector=vector, limit=limit, min_score=min_score)
        pages = [_page_result_from_record(record) for record in records]
        return group_page_results_by_file(pages)

    def _search(self, vector: list[float], limit: int, min_score: float | None) -> list[Any]:
        try:
            response = self._client.query_points(
                collection_name=self._collection,
                query=vector,
                limit=limit,
                with_payload=True,
                score_threshold=min_score,
            )
        except Exception as exc:
            raise ExternalServiceError("Qdrant vector search failed.") from exc
        records = getattr(response, "points", response)
        if not isinstance(records, (list, tuple)):
            raise ExternalServiceError("Qdrant returned an invalid response.")
        return list(records)


def group_page_results_by_file(pages: list[PageSearchResult]) -> list[VectorFileSearchResult]:
    grouped: dict[str, list[PageSearchResult]] = {}
    for page in pages:
        grouped.setdefault(page.google_file_id, []).append(page)

    results: list[VectorFileSearchResult] = []
    for file_id, file_pages in grouped.items():
        sorted_pages = sorted(file_pages, key=lambda page: page.score, reverse=True)
        first = sorted_pages[0]
        expected_metadata = _file_metadata(first)
        if any(_file_metadata(page) != expected_metadata for page in sorted_pages[1:]):
            raise ExternalServiceError(
                f"Qdrant returned inconsistent metadata for google_file_id={file_id}."
            )
        results.append(
            VectorFileSearchResult(
                google_file_id=file_id,
                source_name=first.source_name,
                source_location=first.source_location,
                source_url=first.source_url,
                google_drive_version=first.google_drive_version,
                google_drive_modified_time=first.google_drive_modified_time,
                score=first.score,
                pages=sorted_pages,
            )
        )
    return sorted(results, key=lambda result: result.score, reverse=True)


def _page_result_from_record(record: Any) -> PageSearchResult:
    try:
        payload = record.payload
        if not isinstance(payload, dict):
            raise TypeError("payload must be an object")
        required_strings = (
            "google_file_id",
            "source_name",
            "source_location",
            "source_url",
            "google_drive_version",
            "google_drive_modified_time",
        )
        values: dict[str, str] = {}
        for name in required_strings:
            value = payload.get(name)
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a string")
            if name in {
                "google_file_id",
                "source_name",
                "source_location",
                "google_drive_modified_time",
            } and not value:
                raise TypeError(f"{name} must be a non-empty string")
            values[name] = value
        page_number = payload.get("page_number")
        if isinstance(page_number, bool) or not isinstance(page_number, int) or page_number < 1:
            raise TypeError("page_number must be a positive integer")
        score = record.score
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise TypeError("score must be a number")
        parsed_score = float(score)
        if not math.isfinite(parsed_score):
            raise ValueError("score must be finite")
        return PageSearchResult(
            **values,
            page_number=page_number,
            score=parsed_score,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ExternalServiceError("Qdrant returned an invalid response.") from exc


def _file_metadata(page: PageSearchResult) -> tuple[str, ...]:
    return (
        page.source_name,
        page.source_location,
        page.source_url,
        page.google_drive_version,
        page.google_drive_modified_time,
    )
