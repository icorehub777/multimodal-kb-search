from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FullTextSearchResult:
    google_file_id: str
    name: str
    mime_type: str
    web_url: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PageSearchResult:
    page_number: int
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VectorFileSearchResult:
    google_file_id: str
    source_name: str
    source_location: str
    source_url: str
    google_drive_version: str
    google_drive_modified_time: str
    score: float
    pages: list[PageSearchResult]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["pages"] = [page.to_dict() for page in self.pages]
        return data


@dataclass(frozen=True)
class DownloadedFileResult:
    google_file_id: str
    name: str
    directory: Path
    source_path: Path
    pdf_path: Path | None
    text_paths: list[Path]
    page_paths: list[Path]


@dataclass(frozen=True)
class DownloadFailureResult:
    google_file_id: str
    name: str
    stage: str
    error_type: str
    message: str
    google_drive_url: str
    vector_page_numbers: list[int]
    full_text_query: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProcessedDocument:
    pdf_path: Path | None
    text_paths: list[Path]
    page_paths: list[Path]


@dataclass(frozen=True)
class QueryRunResult:
    bundle: QueryResultBundle
    full_text_count: int
    vector_count: int
    vector_accessible_count: int
    union_count: int
    download_count: int
    downloaded_files: list[DownloadedFileResult]
    download_failure_count: int
    download_failures: list[DownloadFailureResult]


@dataclass(frozen=True)
class QueryResultBundle:
    path: Path
    query_plan_path: Path
    full_text_results_path: Path
    vector_results_path: Path
    download_failures_path: Path
    full_text_results: list[FullTextSearchResult]
    vector_results: list[VectorFileSearchResult]
