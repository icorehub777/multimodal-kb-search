import unittest
from pathlib import Path
from unittest.mock import patch

from kbsearch_cli.errors import ExternalServiceError
from kbsearch_cli.google_drive import GoogleDriveQueryClient


class FakeListRequest:
    def __init__(self, failure=None):
        self.failure = failure

    def execute(self):
        if self.failure is not None:
            raise self.failure
        return {
            "files": [
                {
                    "id": "file-1",
                    "name": "Spec.pdf",
                    "mimeType": "application/pdf",
                    "webViewLink": "https://drive/file-1",
                }
            ]
        }


class FakeFilesResource:
    def __init__(self, failure=None):
        self.list_kwargs = None
        self.failure = failure

    def list(self, **kwargs):
        self.list_kwargs = kwargs
        return FakeListRequest(self.failure)


class FakeDriveService:
    def __init__(self, failure=None):
        self.files_resource = FakeFilesResource(failure)

    def files(self):
        return self.files_resource


class GoogleDriveQueryClientTests(unittest.TestCase):
    def test_search_sends_drive_query_language_without_rewriting(self):
        drive_service = FakeDriveService()
        client = GoogleDriveQueryClient(drive_service)

        results = client.search(
            drive_query="(fullText contains 'ABC' or name contains 'ABC') and trashed = false",
            limit=7,
        )

        self.assertEqual(results[0].google_file_id, "file-1")
        self.assertEqual(
            drive_service.files_resource.list_kwargs["q"],
            "(fullText contains 'ABC' or name contains 'ABC') and trashed = false",
        )
        self.assertEqual(drive_service.files_resource.list_kwargs["pageSize"], 7)

    def test_search_wraps_google_drive_errors(self):
        client = GoogleDriveQueryClient(FakeDriveService(failure=RuntimeError("bad q")))

        with self.assertRaisesRegex(ExternalServiceError, "Google Drive search failed: bad q"):
            client.search(
                drive_query="invalid query",
                limit=7,
            )

    def test_download_wraps_google_drive_errors(self):
        class FakeDownloadFilesResource:
            def get_media(self, fileId, **kwargs):
                return object()

        client = GoogleDriveQueryClient(
            type("Service", (), {"files": lambda self: FakeDownloadFilesResource()})()
        )

        with patch(
            "kbsearch_cli.google_drive._write_request_bytes",
            side_effect=RuntimeError("download denied"),
        ), self.assertRaisesRegex(
            ExternalServiceError,
            "Google Drive download failed \\(file_id=file-1, name=Spec.pdf\\): download denied",
        ):
            client.download("file-1", "Spec.pdf", "application/pdf", Path("C:/tmp/out"))

    def test_download_exports_google_sheet_as_xlsx(self):
        class FakeDownloadFilesResource:
            def __init__(self):
                self.export_kwargs = None

            def export_media(self, **kwargs):
                self.export_kwargs = kwargs
                return b"xlsx-content"

        files_resource = FakeDownloadFilesResource()
        client = GoogleDriveQueryClient(
            type("Service", (), {"files": lambda self: files_resource})()
        )

        with patch("kbsearch_cli.google_drive._write_request_bytes") as write_request:
            output_path = client.download(
                "sheet-1",
                "Orders",
                "application/vnd.google-apps.spreadsheet",
                Path("C:/tmp/out"),
            )

        self.assertEqual(output_path, Path("C:/tmp/out/Orders.xlsx"))
        self.assertEqual(
            files_resource.export_kwargs,
            {
                "fileId": "sheet-1",
                "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            },
        )
        write_request.assert_called_once_with(b"xlsx-content", output_path)

    def test_download_keeps_uploaded_xlsx_as_original_file(self):
        class FakeDownloadFilesResource:
            def __init__(self):
                self.get_media_kwargs = None

            def get_media(self, **kwargs):
                self.get_media_kwargs = kwargs
                return b"xlsx-content"

        files_resource = FakeDownloadFilesResource()
        client = GoogleDriveQueryClient(
            type("Service", (), {"files": lambda self: files_resource})()
        )

        with patch("kbsearch_cli.google_drive._write_request_bytes") as write_request:
            output_path = client.download(
                "xlsx-1",
                "Orders.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                Path("C:/tmp/out"),
            )

        self.assertEqual(output_path, Path("C:/tmp/out/Orders.xlsx"))
        self.assertEqual(
            files_resource.get_media_kwargs,
            {"fileId": "xlsx-1", "supportsAllDrives": True},
        )
        write_request.assert_called_once_with(b"xlsx-content", output_path)


class FakeGetRequest:
    def __init__(self, failure=None, payload=None):
        self.failure = failure
        self.payload = payload or {"id": "file-1"}

    def execute(self):
        if self.failure is not None:
            raise self.failure
        return self.payload


class FakeAccessFilesResource(FakeFilesResource):
    def __init__(self, failure=None):
        super().__init__(failure=failure)
        self.get_kwargs = None

    def get(self, **kwargs):
        self.get_kwargs = kwargs
        return FakeGetRequest(self.failure)


class FakeBatchGetRequest:
    def __init__(self, file_id: str, *, failure: Exception | None = None):
        self.file_id = file_id
        self.failure = failure
        self.get_kwargs: dict[str, object] | None = None
        self.payload = {
            "id": file_id,
            "name": "Spec.pdf",
            "mimeType": "application/pdf",
            "webViewLink": f"https://drive/{file_id}",
        }


class FakeBatchHttpRequest:
    def __init__(self, callback):
        self.callback = callback
        self.requests: list[tuple[str | None, FakeBatchGetRequest]] = []

    def add(self, request, request_id=None):
        self.requests.append((request_id, request))

    def execute(self):
        for request_id, request in self.requests:
            if request.failure is not None:
                self.callback(request_id, None, request.failure)
            else:
                self.callback(request_id, request.payload, None)


class FakeBatchFilesResource:
    def __init__(self, inaccessible_file_ids: set[str] | None = None):
        self.inaccessible_file_ids = inaccessible_file_ids or set()
        self.get_calls: list[dict[str, object]] = []

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        file_id = kwargs["fileId"]
        failure = RuntimeError("not found") if file_id in self.inaccessible_file_ids else None
        request = FakeBatchGetRequest(file_id, failure=failure)
        request.get_kwargs = kwargs
        return request


class FakeBatchDriveService:
    def __init__(self, inaccessible_file_ids: set[str] | None = None):
        self.files_resource = FakeBatchFilesResource(inaccessible_file_ids)

    def files(self):
        return self.files_resource

    def new_batch_http_request(self, callback=None):
        return FakeBatchHttpRequest(callback)


class GoogleDriveAccessTests(unittest.TestCase):
    def test_get_file_metadata_returns_drive_fields(self):
        files_resource = FakeAccessFilesResource()
        files_resource.get = lambda **kwargs: FakeGetRequest(
            payload={
                "id": "file-9",
                "name": "Z.pdf",
                "mimeType": "application/pdf",
                "webViewLink": "https://drive/file-9",
            }
        )
        client = GoogleDriveQueryClient(type("Service", (), {"files": lambda self: files_resource})())

        metadata = client.get_file_metadata("file-9")

        self.assertEqual(metadata.google_file_id, "file-9")
        self.assertEqual(metadata.name, "Z.pdf")
        self.assertEqual(metadata.mime_type, "application/pdf")

    def test_get_file_metadata_wraps_google_drive_errors(self):
        files_resource = FakeAccessFilesResource(failure=RuntimeError("missing"))
        client = GoogleDriveQueryClient(type("Service", (), {"files": lambda self: files_resource})())

        with self.assertRaisesRegex(
            ExternalServiceError,
            "Google Drive metadata lookup failed \\(file_id=file-1\\): missing",
        ):
            client.get_file_metadata("file-1")

    def test_resolve_accessible_metadata_uses_batch_files_get(self):
        drive_service = FakeBatchDriveService()
        client = GoogleDriveQueryClient(drive_service)

        resolved = client.resolve_accessible_metadata(["file-1", "file-2"])

        self.assertEqual(len(drive_service.files_resource.get_calls), 2)
        self.assertTrue(all(call["supportsAllDrives"] for call in drive_service.files_resource.get_calls))
        self.assertEqual(resolved["file-1"].name, "Spec.pdf")
        self.assertEqual(resolved["file-2"].google_file_id, "file-2")

    def test_resolve_accessible_metadata_logs_inaccessible_files(self):
        drive_service = FakeBatchDriveService(inaccessible_file_ids={"file-missing"})
        client = GoogleDriveQueryClient(drive_service)

        resolved = client.resolve_accessible_metadata(["file-1", "file-missing"])

        self.assertEqual(set(resolved.keys()), {"file-1"})


if __name__ == "__main__":
    unittest.main()
