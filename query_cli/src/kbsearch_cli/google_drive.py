from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

from kbsearch_cli.models import FullTextSearchResult

GOOGLE_NATIVE_EXPORT_MIME_TYPES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.presentation",
}
DRIVE_SEARCH_FIELDS = "files(id,name,mimeType,webViewLink)"


class GoogleDriveQueryClient:
    def __init__(self, drive_service: Any) -> None:
        self._drive_service = drive_service

    def search_full_text(self, query: str, limit: int) -> list[FullTextSearchResult]:
        response = self._drive_service.files().list(
            q=f"fullText contains '{_escape_query_term(query)}' and trashed = false",
            fields=DRIVE_SEARCH_FIELDS,
            pageSize=limit,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        return [
            FullTextSearchResult(
                google_file_id=item["id"],
                name=item["name"],
                mime_type=item.get("mimeType", ""),
                web_url=item.get("webViewLink", ""),
            )
            for item in response.get("files", [])
        ]

    def can_access(self, file_id: str) -> bool:
        try:
            self._drive_service.files().get(
                fileId=file_id,
                fields="id",
                supportsAllDrives=True,
            ).execute()
        except Exception:
            return False
        return True

    def download(self, file_id: str, name: str, mime_type: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        if mime_type in GOOGLE_NATIVE_EXPORT_MIME_TYPES:
            output_path = output_dir / f"{safe_download_name(name)}.pdf"
            request = self._drive_service.files().export_media(fileId=file_id, mimeType="application/pdf")
        else:
            output_path = output_dir / safe_download_name(name)
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


def safe_download_name(name: str) -> str:
    return re.sub(r'[<>:"/\\\\|?*]', "_", name).strip() or "downloaded_file"
