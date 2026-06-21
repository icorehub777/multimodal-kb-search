from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class WorkspaceDocument:
    file_id: str
    name: str
    location: str
    web_url: str
    version: str
    modified_time: str
    mime_type: str


@dataclass(frozen=True)
class QdrantDocument:
    file_id: str
    modified_time: str


@dataclass(frozen=True)
class PageVectorMetadata:
    google_file_id: str
    source_name: str
    source_location: str
    source_url: str
    google_drive_version: str
    google_drive_modified_time: str
    page_number: int

    def to_payload(self) -> dict[str, str | int]:
        return {
            "google_file_id": self.google_file_id,
            "source_name": self.source_name,
            "source_location": self.source_location,
            "source_url": self.source_url,
            "google_drive_version": self.google_drive_version,
            "google_drive_modified_time": self.google_drive_modified_time,
            "page_number": self.page_number,
        }
