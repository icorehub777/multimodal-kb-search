from __future__ import annotations

from pathlib import Path

from kbsearch_importer.models import PageVectorMetadata, WorkspaceDocument


def build_page_vector_metadata(
    document: WorkspaceDocument,
    page_number: int,
    page_image_path: Path,
    source_file_path: Path,
) -> PageVectorMetadata:
    if page_number < 1:
        raise ValueError("page_number must be >= 1")

    return PageVectorMetadata(
        google_file_id=document.file_id,
        source_name=document.name,
        source_location=document.location,
        source_url=document.web_url,
        google_drive_version=document.version,
        google_drive_modified_time=document.modified_time,
        page_number=page_number,
        page_image_path=page_image_path,
        source_file_path=source_file_path,
    )
