from __future__ import annotations

from typing import Any

from kbsearch_secure_backend.models import PageSearchResult, VectorFileSearchResult


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

    def _search(self, vector: list[float], limit: int, min_score: float | None) -> Any:
        response = self._client.query_points(
            collection_name=self._collection,
            query=vector,
            limit=limit,
            with_payload=True,
            score_threshold=min_score,
        )
        return getattr(response, "points", response)


def group_page_results_by_file(pages: list[PageSearchResult]) -> list[VectorFileSearchResult]:
    grouped: dict[str, list[PageSearchResult]] = {}
    for page in pages:
        grouped.setdefault(page.google_file_id, []).append(page)

    results: list[VectorFileSearchResult] = []
    for file_id, file_pages in grouped.items():
        sorted_pages = sorted(file_pages, key=lambda page: page.score, reverse=True)
        first = sorted_pages[0]
        results.append(
            VectorFileSearchResult(
                google_file_id=file_id,
                source_name=first.source_name,
                source_location=first.source_location,
                source_url=first.source_url,
                google_drive_version=first.google_drive_version,
                google_drive_modified_time=first.google_drive_modified_time,
                score=sorted_pages[0].score,
                pages=sorted_pages,
            )
        )
    return sorted(results, key=lambda result: result.score, reverse=True)


def _page_result_from_record(record: Any) -> PageSearchResult:
    payload = record.payload or {}
    return PageSearchResult(
        google_file_id=str(payload.get("google_file_id", "")),
        source_name=str(payload.get("source_name", "")),
        source_location=str(payload.get("source_location", "")),
        source_url=str(payload.get("source_url", "")),
        google_drive_version=str(payload.get("google_drive_version", "")),
        google_drive_modified_time=str(payload.get("google_drive_modified_time", "")),
        page_number=int(payload.get("page_number", 0)),
        score=float(record.score),
    )
