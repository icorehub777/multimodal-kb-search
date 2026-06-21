from __future__ import annotations

import io
import logging
import re
from collections import deque
from pathlib import Path
from typing import Any

from app.config import GoogleDriveSource
from app.document_processing import (
    UnsupportedDocumentTypeError,
    is_supported_document_mime_type,
)
from app.logging_config import LOGGER_NAME
from app.models import WorkspaceDocument

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
DRIVE_FOLDER_QUERY = "trashed = false and mimeType = 'application/vnd.google-apps.folder'"
UNSUPPORTED_DOWNLOAD_MIME_TYPES = {
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class GoogleDriveScanner:
    def __init__(
        self,
        drive_service: Any,
        sources: tuple[GoogleDriveSource, ...],
        logger: logging.Logger | None = None,
    ) -> None:
        self._drive_service = drive_service
        self._sources = sources
        self._logger = logger or logging.getLogger(LOGGER_NAME)

    def list_documents(self) -> list[WorkspaceDocument]:
        documents: list[WorkspaceDocument] = []
        for source in self._sources:
            documents.extend(self._list_source_documents(source))
        return documents

    def _list_source_documents(self, source: GoogleDriveSource) -> list[WorkspaceDocument]:
        if source.type == "folder":
            return self._list_folder_source_documents(source)

        page_token: str | None = None
        items: list[dict[str, Any]] = []

        while True:
            response = self._drive_service.files().list(
                **self._list_kwargs(source, page_token),
            ).execute()
            for item in response.get("files", []):
                if item.get("trashed"):
                    continue
                items.append(item)

            page_token = response.get("nextPageToken")
            if not page_token:
                folder_paths = self._shared_drive_folder_paths(source)
                return [
                    _workspace_document_from_item(
                        item,
                        _item_location(source.name, item, folder_paths),
                    )
                    for item in self._supported_items(source, items)
                ]

    def _list_folder_source_documents(self, source: GoogleDriveSource) -> list[WorkspaceDocument]:
        if not source.folder_id:
            raise ValueError(f"Folder source requires folder_id: {source.name}")

        documents: list[WorkspaceDocument] = []
        pending_folders = deque([(source.folder_id, source.name)])
        while pending_folders:
            folder_id, folder_path = pending_folders.popleft()
            file_query = f"'{_escape_query_term(folder_id)}' in parents and {DRIVE_FILE_QUERY}"
            for item in self._supported_items(source, self._list_items(source, file_query)):
                documents.append(_workspace_document_from_item(item, f"{folder_path}/{item['name']}"))

            folder_query = f"'{_escape_query_term(folder_id)}' in parents and {DRIVE_FOLDER_QUERY}"
            for item in self._list_items(source, folder_query):
                pending_folders.append((item["id"], f"{folder_path}/{item['name']}"))

        return documents

    def _supported_items(
        self,
        source: GoogleDriveSource,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        supported: list[dict[str, Any]] = []
        for item in items:
            mime_type = str(item.get("mimeType", ""))
            if is_supported_document_mime_type(mime_type):
                supported.append(item)
                continue
            self._logger.info(
                "file_id=%s name=%s mime_type=%s source=%s "
                "action=skip reason=unsupported_mime_type",
                item.get("id", ""),
                item.get("name", ""),
                mime_type,
                source.name,
            )
        return supported

    def _shared_drive_folder_paths(self, source: GoogleDriveSource) -> dict[str, str]:
        folder_items = {
            item["id"]: item
            for item in self._list_items(source, DRIVE_FOLDER_QUERY)
        }
        resolved: dict[str, str] = {}
        resolving: set[str] = set()

        def folder_path(folder_id: str) -> str:
            if folder_id in resolved:
                return resolved[folder_id]
            if folder_id in resolving:
                return str(folder_items[folder_id]["name"])

            item = folder_items[folder_id]
            resolving.add(folder_id)
            try:
                parent_paths = [
                    folder_path(parent_id)
                    for parent_id in item.get("parents", [])
                    if parent_id in folder_items
                ]
                resolved[folder_id] = (
                    f"{parent_paths[0]}/{item['name']}" if parent_paths else item["name"]
                )
                return resolved[folder_id]
            finally:
                resolving.discard(folder_id)

        return {folder_id: folder_path(folder_id) for folder_id in folder_items}

    def _list_items(self, source: GoogleDriveSource, query: str) -> list[dict[str, Any]]:
        page_token: str | None = None
        items: list[dict[str, Any]] = []
        while True:
            response = self._drive_service.files().list(
                **self._list_kwargs(source, page_token, query=query),
            ).execute()
            items.extend(item for item in response.get("files", []) if not item.get("trashed"))
            page_token = response.get("nextPageToken")
            if not page_token:
                return items

    def _list_kwargs(
        self,
        source: GoogleDriveSource,
        page_token: str | None,
        *,
        query: str | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "q": query or DRIVE_FILE_QUERY,
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
        elif source.type != "folder":
            raise ValueError(f"Unsupported Google Drive source type: {source.type}")

        return kwargs


class GoogleDriveDownloader:
    def __init__(self, drive_service: Any) -> None:
        self._drive_service = drive_service

    def download(self, file_id: str, name: str, mime_type: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        if mime_type in UNSUPPORTED_DOWNLOAD_MIME_TYPES:
            raise UnsupportedDocumentTypeError(
                "Excel files are not directly vectorized. Convert the file to A4 PDF first."
            )

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


def _workspace_document_from_item(item: dict[str, Any], location: str) -> WorkspaceDocument:
    return WorkspaceDocument(
        file_id=item["id"],
        name=item["name"],
        location=location,
        web_url=item.get("webViewLink", ""),
        version=str(item.get("version", "")),
        modified_time=item.get("modifiedTime", ""),
        mime_type=item.get("mimeType", ""),
    )


def _item_location(source_name: str, item: dict[str, Any], folder_paths: dict[str, str]) -> str:
    parent_paths = [
        folder_paths[parent_id]
        for parent_id in item.get("parents", [])
        if parent_id in folder_paths
    ]
    if parent_paths:
        return f"{source_name}/{parent_paths[0]}/{item['name']}"
    return f"{source_name}/{item['name']}"


def _escape_query_term(term: str) -> str:
    return term.replace("\\", "\\\\").replace("'", "\\'")


def _safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\\\|?*]', "_", name).strip() or "downloaded_file"
