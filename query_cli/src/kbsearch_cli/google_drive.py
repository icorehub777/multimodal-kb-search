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
GOOGLE_NATIVE_MIME_PREFIX = "application/vnd.google-apps."
DRIVE_SEARCH_FIELDS = "files(id,name,mimeType,webViewLink,parents,driveId,capabilities/canDownload)"
DRIVE_METADATA_FIELDS = "id,name,mimeType,webViewLink"
DRIVE_PARENT_FIELDS = "id,name,parents"
DRIVE_SHARED_DRIVE_FIELDS = "id,name"


def _metadata_from_drive_item(
    item: dict[str, Any],
    *,
    source_location: str = "",
) -> FullTextSearchResult:
    return FullTextSearchResult(
        google_file_id=item["id"],
        name=item["name"],
        mime_type=item.get("mimeType", ""),
        web_url=item.get("webViewLink", ""),
        source_location=source_location,
    )


class GoogleDriveQueryClient:
    def __init__(self, drive_service: Any) -> None:
        self._drive_service = drive_service
        self._parent_metadata_cache: dict[str, dict[str, Any]] = {}
        self._shared_drive_name_cache: dict[str, str] = {}

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
            _metadata_from_drive_item(
                item,
                source_location=self._source_location_from_item(item),
            )
            for item in response.get("files", [])
            if _is_search_result_downloadable(item)
            and _is_supported_google_native_mime_type(item.get("mimeType", ""))
        ]

    def _source_location_from_item(self, item: dict[str, Any]) -> str:
        names = [str(item.get("name") or "")]
        parent_ids = [str(parent_id) for parent_id in item.get("parents") or []]
        seen_parent_ids: set[str] = set()
        while parent_ids:
            parent_id = parent_ids[0]
            if parent_id in seen_parent_ids:
                break
            seen_parent_ids.add(parent_id)
            parent = self._get_parent_metadata(parent_id)
            parent_name = str(parent.get("name") or "")
            if parent_name:
                names.append(parent_name)
            parent_ids = [str(parent_id) for parent_id in parent.get("parents") or []]
        parts = list(reversed([name for name in names if name]))
        drive_id = str(item.get("driveId") or "")
        if drive_id:
            shared_drive_name = self._get_shared_drive_name(drive_id)
            if parts:
                parts[0] = shared_drive_name
            else:
                parts.append(shared_drive_name)
        return "/".join(parts)

    def _get_parent_metadata(self, parent_id: str) -> dict[str, Any]:
        cached = self._parent_metadata_cache.get(parent_id)
        if cached is not None:
            return cached
        try:
            metadata = self._drive_service.files().get(
                fileId=parent_id,
                fields=DRIVE_PARENT_FIELDS,
                supportsAllDrives=True,
            ).execute()
        except Exception as exc:
            raise ExternalServiceError(
                f"Google Drive parent metadata lookup failed (file_id={parent_id}): {exc}"
            ) from exc
        self._parent_metadata_cache[parent_id] = metadata
        return metadata

    def _get_shared_drive_name(self, drive_id: str) -> str:
        cached = self._shared_drive_name_cache.get(drive_id)
        if cached is not None:
            return cached
        try:
            metadata = self._drive_service.drives().get(
                driveId=drive_id,
                fields=DRIVE_SHARED_DRIVE_FIELDS,
            ).execute()
        except Exception as exc:
            raise ExternalServiceError(
                f"Google Drive shared drive metadata lookup failed (drive_id={drive_id}): {exc}"
            ) from exc
        name = str(metadata.get("name") or "")
        self._shared_drive_name_cache[drive_id] = name
        return name

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


def _is_search_result_downloadable(item: dict[str, Any]) -> bool:
    capabilities = item.get("capabilities") or {}
    return capabilities.get("canDownload") is not False


def _is_supported_google_native_mime_type(mime_type: str) -> bool:
    if not mime_type.startswith(GOOGLE_NATIVE_MIME_PREFIX):
        return True
    return mime_type in GOOGLE_NATIVE_EXPORTS
