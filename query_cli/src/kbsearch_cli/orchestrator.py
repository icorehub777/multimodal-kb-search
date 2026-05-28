from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Protocol

from kbsearch_cli.models import FullTextSearchResult, QueryResultBundle, VectorFileSearchResult
from kbsearch_cli.output import QueryResultWriter, safe_path_name


class GoogleDriveClient(Protocol):
    def search(self, drive_query: str, limit: int) -> list[FullTextSearchResult]:
        raise NotImplementedError

    def can_access(self, file_id: str) -> bool:
        raise NotImplementedError

    def download(self, file_id: str, name: str, mime_type: str, output_dir: Path) -> Path:
        raise NotImplementedError


class BackendClient(Protocol):
    def search(
        self,
        query: str,
        image_paths: list[Path],
        limit: int,
        min_score: float | None,
    ) -> list[VectorFileSearchResult]:
        raise NotImplementedError


class PageRenderer(Protocol):
    def render_pages(self, source_path: Path, output_dir: Path) -> list[Path]:
        raise NotImplementedError


class QueryOrchestrator:
    def __init__(
        self,
        google_drive: GoogleDriveClient,
        backend: BackendClient,
        result_writer: QueryResultWriter,
        page_renderer: PageRenderer,
    ) -> None:
        self._google_drive = google_drive
        self._backend = backend
        self._result_writer = result_writer
        self._page_renderer = page_renderer

    def run(
        self,
        query_name: str,
        vector_query: str,
        drive_query: str,
        limit: int,
        min_score: float | None,
        image_paths: list[Path] | None = None,
    ) -> QueryResultBundle:
        resolved_image_paths = image_paths or []
        with ThreadPoolExecutor(max_workers=2) as executor:
            full_text_future = executor.submit(self._google_drive.search, drive_query, limit)
            vector_future = executor.submit(
                self._backend.search,
                vector_query,
                resolved_image_paths,
                limit,
                min_score,
            )
            full_text_results = full_text_future.result()
            vector_candidates = vector_future.result()

        access_by_file_id = self._can_access_by_file_id(vector_candidates)
        vector_results = [result for result in vector_candidates if access_by_file_id[result.google_file_id]]
        bundle = self._result_writer.create_bundle(
            query_name=query_name,
            query_plan={
                "vector_query": vector_query,
                "drive_query": drive_query,
                "image_paths": [_path_as_posix(path) for path in resolved_image_paths],
                "limit": limit,
                "min_score": min_score,
            },
            full_text_results=full_text_results,
            vector_results=vector_results,
        )
        self._download_intersection_files(bundle, full_text_results, vector_results)
        return bundle

    def _download_intersection_files(
        self,
        bundle: QueryResultBundle,
        full_text_results: list[FullTextSearchResult],
        vector_results: list[VectorFileSearchResult],
    ) -> None:
        full_text_by_id = {result.google_file_id: result for result in full_text_results}
        for vector_result in vector_results:
            full_text_result = full_text_by_id.get(vector_result.google_file_id)
            if full_text_result is None:
                continue
            file_dir = bundle.path / f"{safe_path_name(full_text_result.name)}-{safe_path_name(full_text_result.google_file_id)}"
            file_dir.mkdir(parents=True, exist_ok=False)
            source_path = self._google_drive.download(
                file_id=full_text_result.google_file_id,
                name=full_text_result.name,
                mime_type=full_text_result.mime_type,
                output_dir=file_dir,
            )
            self._page_renderer.render_pages(source_path, file_dir)

    def _can_access_by_file_id(
        self,
        vector_results: list[VectorFileSearchResult],
    ) -> dict[str, bool]:
        file_ids = list(dict.fromkeys(result.google_file_id for result in vector_results))
        if not file_ids:
            return {}
        with ThreadPoolExecutor(max_workers=min(8, len(file_ids))) as executor:
            checks = executor.map(self._google_drive.can_access, file_ids)
        return dict(zip(file_ids, checks))


def _path_as_posix(path: Path | str) -> str:
    if isinstance(path, Path):
        return path.as_posix()
    return str(path).replace("\\", "/")
