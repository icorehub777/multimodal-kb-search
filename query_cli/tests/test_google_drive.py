import unittest

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


if __name__ == "__main__":
    unittest.main()
