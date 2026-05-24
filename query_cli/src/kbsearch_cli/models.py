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
    page_image_path: str
    source_file_path: str
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
class QueryResultBundle:
    path: Path
    full_text_results_path: Path
    vector_results_path: Path
    full_text_results: list[FullTextSearchResult]
    vector_results: list[VectorFileSearchResult]
