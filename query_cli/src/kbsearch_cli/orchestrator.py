from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from kbsearch_cli.errors import QueryCliError
from kbsearch_cli.full_text import extract_full_text_keywords
from kbsearch_cli.logging_config import LOGGER_NAME
from kbsearch_cli.models import (
    DownloadFailureResult,
    DownloadedFileResult,
    FullTextPageSearchResult,
    FullTextSearchResult,
    ProcessedDocument,
    QueryResultBundle,
    QueryRunResult,
    QueryWarningResult,
    VectorFileSearchResult,
)
from kbsearch_cli.output import QueryResultWriter, safe_path_name

logger = logging.getLogger(LOGGER_NAME)
ProgressCallback = Callable[[str, Mapping[str, object]], None]


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


class DocumentProcessor(Protocol):
    def process(
        self,
        source_path: Path,
        mime_type: str,
        output_dir: Path,
        page_numbers: list[int],
        full_text_keywords: list[str] | None = None,
    ) -> ProcessedDocument:
        raise NotImplementedError


@dataclass(frozen=True)
class _DownloadTarget:
    google_file_id: str
    name: str
    mime_type: str
    google_drive_url: str
    vector_page_numbers: list[int]
    full_text_query: str | None
    full_text_keywords: list[str]


@dataclass(frozen=True)
class _DownloadBatchResult:
    downloaded_files: list[DownloadedFileResult]
    failures: list[DownloadFailureResult]
    warnings: list[QueryWarningResult]
    full_text_pages_by_file_id: dict[str, list[FullTextPageSearchResult]]


class QueryOrchestrator:
    def __init__(
        self,
        google_drive: GoogleDriveClient,
        backend: BackendClient,
        result_writer: QueryResultWriter,
        document_processor: DocumentProcessor,
    ) -> None:
        self._google_drive = google_drive
        self._backend = backend
        self._result_writer = result_writer
        self._document_processor = document_processor

    def run(
        self,
        output_dir: Path,
        vector_query: str | None,
        drive_query: str | None,
        limit: int,
        min_score: float | None,
        image_paths: list[Path] | None = None,
        progress: ProgressCallback | None = None,
    ) -> QueryRunResult:
        resolved_image_paths = image_paths or []
        if vector_query is None and drive_query is None and not resolved_image_paths:
            raise QueryCliError(
                "At least one of vector_query, drive_query or image must be provided."
            )
        for image_path in resolved_image_paths:
            if not image_path.is_file():
                raise QueryCliError(f"Query image not found: {image_path}")

        run_vector_search = vector_query is not None or bool(resolved_image_paths)
        run_drive_search = drive_query is not None

        _report(
            progress,
            "search",
            status="started",
            drive_included=run_drive_search,
            vector_included=run_vector_search,
        )
        logger.info(
            "query phase=search started drive_query=%s vector_query=%s image_count=%s "
            "limit=%s min_score=%s drive_included=%s vector_included=%s",
            drive_query,
            vector_query,
            len(resolved_image_paths),
            limit,
            min_score,
            run_drive_search,
            run_vector_search,
        )
        full_text_results, vector_candidates = self._execute_searches(
            drive_query=drive_query,
            vector_query=vector_query,
            image_paths=resolved_image_paths,
            limit=limit,
            min_score=min_score,
            run_drive_search=run_drive_search,
            run_vector_search=run_vector_search,
        )

        logger.info(
            "query phase=search finished full_text_count=%s vector_count=%s "
            "drive_included=%s vector_included=%s",
            len(full_text_results),
            len(vector_candidates),
            run_drive_search,
            run_vector_search,
        )
        _report(
            progress,
            "search",
            status="finished",
            full_text_count=len(full_text_results),
            vector_count=len(vector_candidates),
            drive_included=run_drive_search,
            vector_included=run_vector_search,
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
        full_text_keywords = extract_full_text_keywords(drive_query)
        download_targets = _build_download_targets(
            full_text_results,
            vector_results,
            metadata_by_file_id,
            drive_query,
            full_text_keywords,
        )
        union_breakdown = _union_breakdown(full_text_results, vector_results)
        bundle = self._result_writer.create_bundle(
            output_dir=output_dir,
            query_plan={
                "vector_query": vector_query,
                "drive_query": drive_query,
                "image_paths": (
                    [_path_as_posix(path) for path in resolved_image_paths]
                    if run_vector_search
                    else None
                ),
                "limit": limit,
                "min_score": min_score,
            },
            full_text_results=full_text_results,
            vector_results=vector_results,
        )
        if not download_targets:
            skip_reason = _download_skip_reason(
                vector_candidates=vector_candidates,
                vector_results=vector_results,
                full_text_results=full_text_results,
                run_vector_search=run_vector_search,
                run_drive_search=run_drive_search,
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
        download_batch = self._download_union_files(
            bundle.path,
            download_targets,
            progress=progress,
        )
        full_text_results = _apply_full_text_pages(
            full_text_results,
            download_batch.full_text_pages_by_file_id,
        )
        bundle = replace(bundle, full_text_results=full_text_results)
        self._result_writer.write_full_text_results(bundle, full_text_results)
        self._result_writer.write_download_failures(bundle, download_batch.failures)
        self._result_writer.write_warnings(bundle, download_batch.warnings)
        logger.info(
            "query phase=complete output_dir=%s union_count=%s download_count=%s "
            "download_failure_count=%s warning_count=%s",
            bundle.path,
            len(download_targets),
            len(download_batch.downloaded_files),
            len(download_batch.failures),
            len(download_batch.warnings),
        )
        _report(
            progress,
            "complete",
            status="finished",
            union_count=len(download_targets),
            download_count=len(download_batch.downloaded_files),
            download_failure_count=len(download_batch.failures),
            warning_count=len(download_batch.warnings),
        )
        return QueryRunResult(
            bundle=bundle,
            full_text_count=len(full_text_results),
            vector_count=len(vector_candidates),
            vector_accessible_count=len(vector_results),
            union_count=len(download_targets),
            download_count=len(download_batch.downloaded_files),
            downloaded_files=download_batch.downloaded_files,
            download_failure_count=len(download_batch.failures),
            download_failures=download_batch.failures,
            warning_count=len(download_batch.warnings),
            warnings=download_batch.warnings,
        )

    def _execute_searches(
        self,
        *,
        drive_query: str | None,
        vector_query: str | None,
        image_paths: list[Path],
        limit: int,
        min_score: float | None,
        run_drive_search: bool,
        run_vector_search: bool,
    ) -> tuple[list[FullTextSearchResult], list[VectorFileSearchResult]]:
        vector_query_text = vector_query if vector_query is not None else ""
        if run_drive_search and run_vector_search:
            with ThreadPoolExecutor(max_workers=2) as executor:
                full_text_future = executor.submit(
                    self._google_drive.search, drive_query, limit
                )
                vector_future = executor.submit(
                    self._backend.search,
                    vector_query_text,
                    image_paths,
                    limit,
                    min_score,
                )
                return full_text_future.result(), vector_future.result()

        full_text_results: list[FullTextSearchResult] = []
        vector_candidates: list[VectorFileSearchResult] = []
        if run_drive_search:
            full_text_results = self._google_drive.search(drive_query, limit)
        if run_vector_search:
            vector_candidates = self._backend.search(
                vector_query_text,
                image_paths,
                limit,
                min_score,
            )
        return full_text_results, vector_candidates

    def _download_union_files(
        self,
        bundle_path: Path,
        download_targets: list[_DownloadTarget],
        *,
        progress: ProgressCallback | None = None,
    ) -> _DownloadBatchResult:
        downloaded_files: list[DownloadedFileResult] = []
        failures: list[DownloadFailureResult] = []
        warnings: list[QueryWarningResult] = []
        full_text_pages_by_file_id: dict[str, list[FullTextPageSearchResult]] = {}
        used_dir_names: set[str] = set()
        total = len(download_targets)
        for index, target in enumerate(download_targets, start=1):
            name = target.name
            mime_type = target.mime_type
            stage = "metadata"
            try:
                if not mime_type:
                    metadata = self._google_drive.get_file_metadata(target.google_file_id)
                    name = metadata.name
                    mime_type = metadata.mime_type
                stage = "prepare_directory"
                file_dir_name = _build_unique_file_dir_name(
                    file_name=name,
                    google_file_id=target.google_file_id,
                    used_dir_names=used_dir_names,
                )
                file_dir = bundle_path / file_dir_name
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
                stage = "download"
                source_path = self._google_drive.download(
                    file_id=target.google_file_id,
                    name=name,
                    mime_type=mime_type,
                    output_dir=file_dir,
                )
                stage = "process"
                processed = self._document_processor.process(
                    source_path,
                    mime_type,
                    file_dir,
                    target.vector_page_numbers,
                    target.full_text_keywords,
                )
                if target.full_text_query is not None:
                    full_text_pages_by_file_id[target.google_file_id] = (
                        processed.full_text_pages
                    )
                if target.vector_page_numbers and not processed.page_paths:
                    warning = QueryWarningResult(
                        code="vector_pages_unrendered",
                        google_file_id=target.google_file_id,
                        name=name,
                        mime_type=mime_type,
                        google_drive_url=target.google_drive_url,
                        vector_page_numbers=target.vector_page_numbers,
                        message=(
                            "Vector search matched pages, but no page images were "
                            "rendered for this file."
                        ),
                    )
                    warnings.append(warning)
                    logger.warning(
                        "query phase=process warning=vector_pages_unrendered "
                        "file_id=%s name=%s mime_type=%s vector_page_numbers=%s",
                        target.google_file_id,
                        name,
                        mime_type,
                        target.vector_page_numbers,
                    )
            except Exception as exc:
                logger.exception(
                    "query phase=download failed file_id=%s name=%s stage=%s "
                    "error=%s message=%s",
                    target.google_file_id,
                    name,
                    stage,
                    exc.__class__.__name__,
                    exc,
                )
                failure = DownloadFailureResult(
                    google_file_id=target.google_file_id,
                    name=name,
                    stage=stage,
                    error_type=exc.__class__.__name__,
                    message=str(exc) or exc.__class__.__name__,
                    google_drive_url=target.google_drive_url,
                    vector_page_numbers=target.vector_page_numbers,
                    full_text_query=target.full_text_query,
                )
                failures.append(failure)
                _report(
                    progress,
                    "download",
                    status="failed",
                    file_id=target.google_file_id,
                    name=name,
                    stage=stage,
                    error_type=failure.error_type,
                    message=failure.message,
                    index=index,
                    total=total,
                )
                continue
            logger.info(
                "query phase=download finished file_id=%s name=%s text_page_count=%s "
                "rendered_page_count=%s",
                target.google_file_id,
                name,
                len(processed.text_paths),
                len(processed.page_paths),
            )
            _report(
                progress,
                "download",
                status="finished",
                file_id=target.google_file_id,
                name=name,
                text_page_count=len(processed.text_paths),
                rendered_page_count=len(processed.page_paths),
                index=index,
                total=total,
            )
            downloaded_files.append(
                DownloadedFileResult(
                    google_file_id=target.google_file_id,
                    name=name,
                    directory=file_dir,
                    source_path=source_path,
                    pdf_path=processed.pdf_path,
                    text_paths=processed.text_paths,
                    page_paths=processed.page_paths,
                )
            )
        return _DownloadBatchResult(
            downloaded_files=downloaded_files,
            failures=failures,
            warnings=warnings,
            full_text_pages_by_file_id=full_text_pages_by_file_id,
        )


def _build_download_targets(
    full_text_results: list[FullTextSearchResult],
    vector_results: list[VectorFileSearchResult],
    metadata_by_file_id: dict[str, FullTextSearchResult],
    drive_query: str | None,
    full_text_keywords: list[str],
) -> list[_DownloadTarget]:
    full_text_by_id = {
        result.google_file_id: result for result in full_text_results
    }
    vector_by_id = {
        result.google_file_id: result for result in vector_results
    }
    ordered_ids = list(
        dict.fromkeys(
            [result.google_file_id for result in vector_results]
            + [result.google_file_id for result in full_text_results]
        )
    )
    targets: list[_DownloadTarget] = []
    for file_id in ordered_ids:
        full_text_result = full_text_by_id.get(file_id)
        vector_result = vector_by_id.get(file_id)
        metadata = metadata_by_file_id.get(file_id)
        reference = full_text_result or metadata
        if reference is None:
            continue
        google_drive_url = reference.web_url
        if not google_drive_url and vector_result is not None:
            google_drive_url = vector_result.source_url
        targets.append(
            _DownloadTarget(
                google_file_id=file_id,
                name=reference.name,
                mime_type=reference.mime_type,
                google_drive_url=google_drive_url,
                vector_page_numbers=(
                    sorted({page.page_number for page in vector_result.pages})
                    if vector_result is not None
                    else []
                ),
                full_text_query=drive_query if full_text_result is not None else None,
                full_text_keywords=(
                    full_text_keywords if full_text_result is not None else []
                ),
            )
        )
    return targets


def _apply_full_text_pages(
    full_text_results: list[FullTextSearchResult],
    full_text_pages_by_file_id: dict[str, list[FullTextPageSearchResult]],
) -> list[FullTextSearchResult]:
    return [
        replace(
            result,
            pages=full_text_pages_by_file_id.get(result.google_file_id, []),
        )
        for result in full_text_results
    ]


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
    *,
    run_vector_search: bool,
    run_drive_search: bool,
) -> str:
    if not run_drive_search and not vector_candidates:
        return "vector_search_no_results"
    if not run_vector_search and not full_text_results:
        return "drive_search_no_results"
    if not full_text_results and not vector_candidates:
        return "no_full_text_or_vector_results"
    if not full_text_results and not vector_results:
        return "all_vector_results_inaccessible"
    return "no_download_targets"


def _path_as_posix(path: Path | str) -> str:
    if isinstance(path, Path):
        return path.as_posix()
    return str(path).replace("\\", "/")


def _build_unique_file_dir_name(
    file_name: str,
    google_file_id: str,
    *,
    used_dir_names: set[str],
    start_length: int = 5,
) -> str:
    safe_file_name = safe_path_name(file_name).strip(" .")
    safe_file_id = safe_path_name(google_file_id).strip(" .")
    prefix_length = min(start_length, len(safe_file_id))
    while True:
        id_prefix = safe_file_id[:prefix_length].strip(" .")
        if not id_prefix:
            id_prefix = "file"
        candidate = f"{safe_file_name}-{id_prefix}"
        if candidate not in used_dir_names:
            used_dir_names.add(candidate)
            return candidate
        if prefix_length >= len(safe_file_id):
            suffix = 2
            while True:
                fallback = f"{safe_file_name}-{safe_file_id}-{suffix}"
                if fallback not in used_dir_names:
                    used_dir_names.add(fallback)
                    return fallback
                suffix += 1
        prefix_length += 1


def _report(
    progress: ProgressCallback | None,
    phase: str,
    **fields: object,
) -> None:
    if progress is not None:
        progress(phase, fields)
