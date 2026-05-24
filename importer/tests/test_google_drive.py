import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from kbsearch_importer.config import GoogleDriveSource
from kbsearch_importer.google_drive import GoogleDriveDownloader, GoogleDriveScanner


class FakeExecute:
    def __init__(self, response):
        self.response = response

    def execute(self):
        return self.response


class FakeFilesResource:
    def __init__(self):
        self.list_calls = []
        self.export_calls = []
        self.get_calls = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return FakeExecute(
            {
                "files": [
                    {
                        "id": "file-1",
                        "name": "Spec.pdf",
                        "mimeType": "application/pdf",
                        "webViewLink": "https://drive.google.com/file/d/file-1",
                        "version": "7",
                        "modifiedTime": "2026-05-24T00:00:00Z",
                    }
                ]
            }
        )

    def export_media(self, **kwargs):
        self.export_calls.append(kwargs)
        return b"pdf"

    def get_media(self, **kwargs):
        self.get_calls.append(kwargs)
        return b"file"


class FakeDriveService:
    def __init__(self):
        self.files_resource = FakeFilesResource()

    def files(self):
        return self.files_resource


class GoogleDriveTests(unittest.TestCase):
    def test_scanner_lists_shared_drive_documents_as_workspace_documents(self):
        service = FakeDriveService()
        scanner = GoogleDriveScanner(
            drive_service=service,
            sources=(GoogleDriveSource(name="shared", type="shared_drive", drive_id="drive-1"),),
        )

        documents = scanner.list_documents()

        self.assertEqual(documents[0].file_id, "file-1")
        self.assertEqual(documents[0].name, "Spec.pdf")
        self.assertEqual(documents[0].version, "7")
        self.assertEqual(documents[0].mime_type, "application/pdf")
        self.assertEqual(service.files_resource.list_calls[0]["driveId"], "drive-1")
        self.assertEqual(service.files_resource.list_calls[0]["corpora"], "drive")
        self.assertIn("mimeType !=", service.files_resource.list_calls[0]["q"])
        self.assertIn("application/vnd.google-apps.spreadsheet", service.files_resource.list_calls[0]["q"])
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            service.files_resource.list_calls[0]["q"],
        )

    def test_scanner_lists_folder_source_documents_without_returning_folders(self):
        service = FakeDriveService()
        scanner = GoogleDriveScanner(
            drive_service=service,
            sources=(GoogleDriveSource(name="folder", type="folder", folder_id="folder-1"),),
        )

        scanner.list_documents()

        query = service.files_resource.list_calls[0]["q"]
        self.assertIn("'folder-1' in parents", query)
        self.assertIn("mimeType !=", query)

    def test_downloader_exports_google_native_docs_as_pdf(self):
        service = FakeDriveService()
        downloader = GoogleDriveDownloader(service)

        with TemporaryDirectory() as temp_dir:
            output = downloader.download(
                file_id="file-1",
                name="Doc",
                mime_type="application/vnd.google-apps.document",
                output_dir=Path(temp_dir),
            )

        self.assertEqual(output.name, "Doc.pdf")
        self.assertEqual(service.files_resource.export_calls[0]["mimeType"], "application/pdf")

    def test_downloader_does_not_export_google_sheets_as_pdf(self):
        service = FakeDriveService()
        downloader = GoogleDriveDownloader(service)

        with TemporaryDirectory() as temp_dir:
            output = downloader.download(
                file_id="file-1",
                name="Sheet",
                mime_type="application/vnd.google-apps.spreadsheet",
                output_dir=Path(temp_dir),
            )

        self.assertEqual(output.name, "Sheet")
        self.assertEqual(service.files_resource.export_calls, [])
        self.assertEqual(service.files_resource.get_calls[0]["fileId"], "file-1")


if __name__ == "__main__":
    unittest.main()
