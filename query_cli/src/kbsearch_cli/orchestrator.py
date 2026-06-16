from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from kbsearch_cli.errors import QueryCliError
from kbsearch_cli.logging_config import LOGGER_NAME
from kbsearch_cli.models import (
    DownloadedFileResult,
    FullTextSearchResult,
    QueryResultBundle,
    QueryRunResult,
    VectorFileSearchResult,
)
from kbsearch_cli.output import QueryResultWriter, safe_path_name

logger = logging.getLogger(LOGGER_NAME)
ProgressCallback = Callable[[str, Mapping[str, object]], None]
SPREADSHEET_EXTENSIONS = {".xls", ".xlsx"}


class GoogleDriveClient(Protocol):
    def search(self, drive_query: str, limit: int) -> list[FullTextSearchResult]:
        raise NotImplementedError

    def resolve_accessible_metadata(
        self,
        file_ids: list[str],
    ) -> dict[str, FullTextSearchResult]:
        raise NotImplementedError

    def get_file_metadata(self, file_id: str) -> FullTextSearchResult:
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


@dataclass(frozen=True)
class _DownloadTarget:
    google_file_id: str
    name: str
    mime_type: str


class QueryOrchestrator:
    def __init__(
        self,
        google_drive: GoogleDriveClient,
        backend: BackendClient,
        result_writer: QueryResultWriter,
        page_renderer: PageRenderer | None,
    ) -> None:
        self._google_drive = google_drive
        self._backend = backend
        self._result_writer = result_writer
        self._page_renderer = page_renderer

    def run(
        self,
        output_dir: Path,
        vector_query: str,
        drive_query: str,
        limit: int,
        min_score: float | None,
        image_paths: list[Path] | None = None,
        progress: ProgressCallback | None = None,
    ) -> QueryRunResult:
        resolved_image_paths = image_paths or []
        for image_path in resolved_image_paths:
            if not image_path.is_file():
                raise QueryCliError(f"Query image not found: {image_path}")

        _report(progress, "search", status="started")
        logger.info(
            "query phase=search started drive_query=%s vector_query=%s image_count=%s limit=%s min_score=%s",
            drive_query,
            vector_query,
            len(resolved_image_paths),
            limit,
            min_score,
        )
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

        logger.info(
            "query phase=search finished full_text_count=%s vector_count=%s",
            len(full_text_results),
            len(vector_candidates),
        )
        _report(
            progress,
            "search",
            status="finished",
            full_text_count=len(full_text_results),
            vector_count=len(vector_candidates),
        )

        vector_file_ids = list(dict.fromkeys(result.google_file_id for result in vector_candidates))
        _report(progress, "access_check", status="started", file_id_count=len(vector_file_ids))
        logger.info(
            "query phase=access_check started file_id_count=%s",
            len(vector_file_ids),
        )
        metadata_by_file_id = self._google_drive.resolve_accessible_metadata(vector_file_ids)
        checked_count = len(vector_file_ids)
        accessible_count = len(metadata_by_file_id)
        logger.info(
            "query phase=access_check finished checked_count=%s accessible_count=%s inaccessible_count=%s",
            checked_count,
            accessible_count,
            checked_count - accessible_count,
        )
        _report(
            progress,
            "access_check",
            status="finished",
            checked_count=checked_count,
            accessible_count=accessible_count,
            inaccessible_count=checked_count - accessible_count,
        )
        for file_id in vector_file_ids:
            if file_id not in metadata_by_file_id:
                logger.warning(
                    "query phase=access_check file_id=%s accessible=false",
                    file_id,
                )

        vector_results = [
            result
            for result in vector_candidates
            if result.google_file_id in metadata_by_file_id
        ]
        download_targets = _build_download_targets(
            full_text_results,
            vector_results,
            metadata_by_file_id,
        )
        union_breakdown = _union_breakdown(full_text_results, vector_results)
        bundle = self._result_writer.create_bundle(
            output_dir=output_dir,
            query_plan={
                "vector_query": vector_query,
                "drive_query": drive_query,
                "image_paths": [_path_as_posix(path) for path in resolved_image_paths],
                "limit": limit,
                "min_score": min_score,
                "render_downloaded_files": self._page_renderer is not None,
            },
            full_text_results=full_text_results,
            vector_results=vector_results,
        )
        if not download_targets:
            skip_reason = _download_skip_reason(
                vector_candidates=vector_candidates,
                vector_results=vector_results,
                full_text_results=full_text_results,
            )
            _report(
                progress,
                "download",
                status="skipped",
                reason=skip_reason,
                union_count=0,
            )
            logger.warning(
                "query phase=download skipped reason=%s full_text_count=%s vector_count=%s "
                "vector_accessible_count=%s union_count=0",
                skip_reason,
                len(full_text_results),
                len(vector_candidates),
                len(vector_results),
            )
        else:
            _report(
                progress,
                "download",
                status="started",
                union_count=len(download_targets),
                full_text_only_count=union_breakdown.full_text_only_count,
                vector_only_count=union_breakdown.vector_only_count,
                both_count=union_breakdown.both_count,
            )
            logger.info(
                "query phase=download started union_count=%s full_text_only_count=%s "
                "vector_only_count=%s both_count=%s",
                len(download_targets),
                union_breakdown.full_text_only_count,
                union_breakdown.vector_only_count,
                union_breakdown.both_count,
            )
        downloaded_files = self._download_union_files(
            bundle.path,
            download_targets,
            progress=progress,
        )
        logger.info(
            "query phase=complete output_dir=%s union_count=%s download_count=%s",
            bundle.path,
            len(download_targets),
            len(downloaded_files),
        )
        _report(
            progress,
            "complete",
            status="finished",
            union_count=len(download_targets),
            download_count=len(downloaded_files),
        )
        return QueryRunResult(
            bundle=bundle,
            full_text_count=len(full_text_results),
            vector_count=len(vector_candidates),
            vector_accessible_count=len(vector_results),
            union_count=len(download_targets),
            download_count=len(downloaded_files),
            downloaded_files=downloaded_files,
        )

    def _download_union_files(
        self,
        bundle_path: Path,
        download_targets: list[_DownloadTarget],
        *,
        progress: ProgressCallback | None = None,
    ) -> list[DownloadedFileResult]:
        downloaded_files: list[DownloadedFileResult] = []
        total = len(download_targets)
        for index, target in enumerate(download_targets, start=1):
            name = target.name
            mime_type = target.mime_type
            if not mime_type:
                metadata = self._google_drive.get_file_metadata(target.google_file_id)
                name = metadata.name
                mime_type = metadata.mime_type
            file_dir = bundle_path / f"{safe_path_name(name)}-{safe_path_name(target.google_file_id)}"
            file_dir.mkdir(parents=True, exist_ok=False)
            _report(
                progress,
                "download",
                status="started",
                file_id=target.google_file_id,
                name=name,
                index=index,
                total=total,
            )
            logger.info(
                "query phase=download started file_id=%s name=%s",
                target.google_file_id,
                name,
            )
            try:
                source_path = self._google_drive.download(
                    file_id=target.google_file_id,
                    name=name,
                    mime_type=mime_type,
                    output_dir=file_dir,
                )
                page_paths = []
                if self._page_renderer is not None and source_path.suffix.lower() not in SPREADSHEET_EXTENSIONS:
                    page_paths = self._page_renderer.render_pages(source_path, file_dir)
                elif self._page_renderer is not None:
                    logger.info(
                        "query phase=download rendering_skipped file_id=%s name=%s reason=spreadsheet",
                        target.google_file_id,
                        name,
                    )
            except Exception as exc:
                logger.exception(
                    "query phase=download failed file_id=%s name=%s error=%s message=%s",
                    target.google_file_id,
                    name,
                    exc.__class__.__name__,
                    exc,
                )
                raise
            logger.info(
                "query phase=download finished file_id=%s name=%s page_count=%s",
                target.google_file_id,
                name,
                len(page_paths),
            )
            _report(
                progress,
                "download",
                status="finished",
                file_id=target.google_file_id,
                name=name,
                page_count=len(page_paths),
                index=index,
                total=total,
            )
            downloaded_files.append(
                DownloadedFileResult(
                    google_file_id=target.google_file_id,
                    name=name,
                    directory=file_dir,
                    source_path=source_path,
                    page_paths=page_paths,
                )
            )
        return downloaded_files


def _build_download_targets(
    full_text_results: list[FullTextSearchResult],
    vector_results: list[VectorFileSearchResult],
    metadata_by_file_id: dict[str, FullTextSearchResult],
) -> list[_DownloadTarget]:
    targets_by_id: dict[str, _DownloadTarget] = {}
    for result in full_text_results:
        targets_by_id[result.google_file_id] = _DownloadTarget(
            google_file_id=result.google_file_id,
            name=result.name,
            mime_type=result.mime_type,
        )
    for result in vector_results:
        if result.google_file_id in targets_by_id:
            continue
        metadata = metadata_by_file_id[result.google_file_id]
        targets_by_id[result.google_file_id] = _DownloadTarget(
            google_file_id=result.google_file_id,
            name=metadata.name,
            mime_type=metadata.mime_type,
        )
    ordered_ids = list(
        dict.fromkeys(
            [result.google_file_id for result in full_text_results]
            + [result.google_file_id for result in vector_results]
        )
    )
    return [targets_by_id[file_id] for file_id in ordered_ids if file_id in targets_by_id]


@dataclass(frozen=True)
class _UnionBreakdown:
    both_count: int
    full_text_only_count: int
    vector_only_count: int


def _union_breakdown(
    full_text_results: list[FullTextSearchResult],
    vector_results: list[VectorFileSearchResult],
) -> _UnionBreakdown:
    full_text_ids = {result.google_file_id for result in full_text_results}
    vector_ids = {result.google_file_id for result in vector_results}
    both_ids = full_text_ids & vector_ids
    return _UnionBreakdown(
        both_count=len(both_ids),
        full_text_only_count=len(full_text_ids - vector_ids),
        vector_only_count=len(vector_ids - full_text_ids),
    )


def _download_skip_reason(
    vector_candidates: list[VectorFileSearchResult],
    vector_results: list[VectorFileSearchResult],
    full_text_results: list[FullTextSearchResult],
) -> str:
    if not full_text_results and not vector_candidates:
        return "no_full_text_or_vector_results"
    if not full_text_results and not vector_results:
        return "all_vector_results_inaccessible"
    return "no_download_targets"


def _path_as_posix(path: Path | str) -> str:
    if isinstance(path, Path):
        return path.as_posix()
    return str(path).replace("\\", "/")


def _report(
    progress: ProgressCallback | None,
    phase: str,
    **fields: object,
) -> None:
    if progress is not None:
        progress(phase, fields)
