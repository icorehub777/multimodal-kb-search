from __future__ import annotations

from pydantic import BaseModel, Field


class PageSearchResult(BaseModel):
    google_file_id: str
    source_name: str
    source_location: str
    source_url: str
    google_drive_version: str
    google_drive_modified_time: str
    page_number: int
    score: float


class VectorFileSearchResult(BaseModel):
    google_file_id: str
    source_name: str
    source_location: str
    source_url: str
    google_drive_version: str
    google_drive_modified_time: str
    score: float
    pages: list[PageSearchResult]


class QueryImage(BaseModel):
    filename: str
    mime_type: str
    base64_data: str


class VectorSearchRequest(BaseModel):
    query: str = ""
    images: list[QueryImage] = Field(default_factory=list)
    limit: int = 10
    min_score: float | None = None


class VectorSearchResponse(BaseModel):
    results: list[VectorFileSearchResult]


class ErrorResponse(BaseModel):
    error: str
    message: str
