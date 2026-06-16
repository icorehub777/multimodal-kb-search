from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from kbsearch_cli.errors import ExternalServiceError
from kbsearch_cli.logging_config import LOGGER_NAME
from kbsearch_cli.models import FullTextSearchResult

logger = logging.getLogger(LOGGER_NAME)

GOOGLE_NATIVE_EXPORTS = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
}
DRIVE_SEARCH_FIELDS = "files(id,name,mimeType,webViewLink)"
DRIVE_METADATA_FIELDS = "id,name,mimeType,webViewLink"


def _metadata_from_drive_item(item: dict[str, Any]) -> FullTextSearchResult:
    return FullTextSearchResult(
        google_file_id=item["id"],
        name=item["name"],
        mime_type=item.get("mimeType", ""),
        web_url=item.get("webViewLink", ""),
    )


class GoogleDriveQueryClient:
    def __init__(self, drive_service: Any) -> None:
        self._drive_service = drive_service

    def search(self, drive_query: str, limit: int) -> list[FullTextSearchResult]:
        try:
            response = self._drive_service.files().list(
                q=drive_query,
                fields=DRIVE_SEARCH_FIELDS,
                pageSize=limit,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
        except Exception as exc:
            raise ExternalServiceError(f"Google Drive search failed: {exc}") from exc
        return [
            FullTextSearchResult(
                google_file_id=item["id"],
                name=item["name"],
                mime_type=item.get("mimeType", ""),
                web_url=item.get("webViewLink", ""),
            )
            for item in response.get("files", [])
        ]

    def resolve_accessible_metadata(
        self,
        file_ids: list[str],
    ) -> dict[str, FullTextSearchResult]:
        unique_file_ids = list(dict.fromkeys(file_ids))
        if not unique_file_ids:
            return {}

        resolved: dict[str, FullTextSearchResult] = {}

        def _batch_callback(
            request_id: str | None,
            response: dict[str, Any] | None,
            exception: Exception | None,
        ) -> None:
            file_id = str(request_id)
            if exception is not None:
                logger.warning(
                    "Google Drive access check failed file_id=%s: %s",
                    file_id,
                    exception,
                )
                return
            if response is None:
                logger.warning(
                    "Google Drive access check failed file_id=%s: empty batch response",
                    file_id,
                )
                return
            resolved[file_id] = _metadata_from_drive_item(response)

        try:
            batch = self._drive_service.new_batch_http_request(callback=_batch_callback)
            for file_id in unique_file_ids:
                batch.add(
                    self._drive_service.files().get(
                        fileId=file_id,
                        fields=DRIVE_METADATA_FIELDS,
                        supportsAllDrives=True,
                    ),
                    request_id=file_id,
                )
            batch.execute()
        except Exception as exc:
            raise ExternalServiceError(
                "Google Drive metadata batch lookup failed "
                f"(file_id_count={len(unique_file_ids)}): {exc}"
            ) from exc

        return resolved

    def get_file_metadata(self, file_id: str) -> FullTextSearchResult:
        try:
            item = self._drive_service.files().get(
                fileId=file_id,
                fields=DRIVE_METADATA_FIELDS,
                supportsAllDrives=True,
            ).execute()
        except Exception as exc:
            raise ExternalServiceError(
                f"Google Drive metadata lookup failed (file_id={file_id}): {exc}"
            ) from exc
        return _metadata_from_drive_item(item)

    def download(self, file_id: str, name: str, mime_type: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            native_export = GOOGLE_NATIVE_EXPORTS.get(mime_type)
            if native_export is not None:
                export_mime_type, output_extension = native_export
                output_path = output_dir / f"{safe_download_name(name)}{output_extension}"
                request = self._drive_service.files().export_media(
                    fileId=file_id,
                    mimeType=export_mime_type,
                )
            else:
                output_path = output_dir / safe_download_name(name)
                request = self._drive_service.files().get_media(
                    fileId=file_id,
                    supportsAllDrives=True,
                )
            _write_request_bytes(request, output_path)
        except Exception as exc:
            raise ExternalServiceError(
                f"Google Drive download failed (file_id={file_id}, name={name}): {exc}"
            ) from exc
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


def safe_download_name(name: str) -> str:
    return re.sub(r'[<>:"/\\\\|?*]', "_", name).strip() or "downloaded_file"
