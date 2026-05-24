from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

from kbsearch_importer.config import GoogleDriveSource
from kbsearch_importer.models import WorkspaceDocument

GOOGLE_NATIVE_EXPORT_MIME_TYPES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.presentation",
}

DRIVE_FILE_FIELDS = "nextPageToken,files(id,name,mimeType,parents,webViewLink,version,modifiedTime,trashed)"
UNSUPPORTED_SCAN_MIME_TYPES = (
    "application/vnd.google-apps.folder",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
DRIVE_FILE_QUERY = "trashed = false and " + " and ".join(
    f"mimeType != '{mime_type}'" for mime_type in UNSUPPORTED_SCAN_MIME_TYPES
)


class GoogleDriveScanner:
    def __init__(self, drive_service: Any, sources: tuple[GoogleDriveSource, ...]) -> None:
        self._drive_service = drive_service
        self._sources = sources

    def list_documents(self) -> list[WorkspaceDocument]:
        documents: list[WorkspaceDocument] = []
        for source in self._sources:
            documents.extend(self._list_source_documents(source))
        return documents

    def _list_source_documents(self, source: GoogleDriveSource) -> list[WorkspaceDocument]:
        page_token: str | None = None
        documents: list[WorkspaceDocument] = []

        while True:
            response = self._drive_service.files().list(
                **self._list_kwargs(source, page_token),
            ).execute()
            for item in response.get("files", []):
                if item.get("trashed"):
                    continue
                documents.append(
                    WorkspaceDocument(
                        file_id=item["id"],
                        name=item["name"],
                        location=f"{source.name}/{item['name']}",
                        web_url=item.get("webViewLink", ""),
                        version=str(item.get("version", "")),
                        modified_time=item.get("modifiedTime", ""),
                        mime_type=item.get("mimeType", ""),
                    )
                )

            page_token = response.get("nextPageToken")
            if not page_token:
                return documents

    def _list_kwargs(self, source: GoogleDriveSource, page_token: str | None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "q": DRIVE_FILE_QUERY,
            "fields": DRIVE_FILE_FIELDS,
            "pageSize": 1000,
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
        }
        if page_token:
            kwargs["pageToken"] = page_token

        if source.type == "shared_drive":
            kwargs["corpora"] = "drive"
            kwargs["driveId"] = source.drive_id
        elif source.type == "folder":
            kwargs["q"] = f"'{_escape_query_term(source.folder_id or '')}' in parents and {DRIVE_FILE_QUERY}"
        else:
            raise ValueError(f"Unsupported Google Drive source type: {source.type}")

        return kwargs


class GoogleDriveDownloader:
    def __init__(self, drive_service: Any) -> None:
        self._drive_service = drive_service

    def download(self, file_id: str, name: str, mime_type: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        if mime_type in GOOGLE_NATIVE_EXPORT_MIME_TYPES:
            output_path = output_dir / f"{_safe_filename(name)}.pdf"
            request = self._drive_service.files().export_media(
                fileId=file_id,
                mimeType="application/pdf",
            )
        else:
            output_path = output_dir / _safe_filename(name)
            request = self._drive_service.files().get_media(fileId=file_id)

        _write_request_bytes(request, output_path)
        return output_path


def _write_request_bytes(request: Any, output_path: Path) -> None:
    if isinstance(request, bytes):
        output_path.write_bytes(request)
        return

    try:
        from googleapiclient.http import MediaIoBaseDownload
    except ImportError as exc:
        raise RuntimeError("google-api-python-client is required for Google Drive downloads.") from exc

    with output_path.open("wb") as output_file:
        downloader = MediaIoBaseDownload(output_file, request)
        done = False
        while not done:
            _status, done = downloader.next_chunk()


def _escape_query_term(term: str) -> str:
    return term.replace("\\", "\\\\").replace("'", "\\'")


def _safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\\\|?*]', "_", name).strip() or "downloaded_file"
