import unittest

from kbsearch_backend.errors import ExternalServiceError
from kbsearch_backend.models import PageSearchResult
from kbsearch_backend.qdrant_search import QdrantSearchAdapter, group_page_results_by_file


class FakeQdrantClient:
    def __init__(self):
        self.calls = []

    def query_points(self, **kwargs):
        self.calls.append(kwargs)
        return type("Response", (), {"points": [
            type(
                "Record",
                (),
                {
                    "score": 0.7,
                    "payload": {
                        "google_file_id": "file-2",
                        "source_name": "Beta.pdf",
                        "source_location": "Drive/Beta.pdf",
                        "source_url": "https://drive/file-2",
                        "google_drive_version": "3",
                        "google_drive_modified_time": "2026-05-24T00:00:00Z",
                        "page_number": 2,
                    },
                },
            )(),
            type(
                "Record",
                (),
                {
                    "score": 0.9,
                    "payload": {
                        "google_file_id": "file-1",
                        "source_name": "Alpha.pdf",
                        "source_location": "Drive/Alpha.pdf",
                        "source_url": "https://drive/file-1",
                        "google_drive_version": "8",
                        "google_drive_modified_time": "2026-05-24T00:00:00Z",
                        "page_number": 3,
                    },
                },
            )(),
            type(
                "Record",
                (),
                {
                    "score": 0.8,
                    "payload": {
                        "google_file_id": "file-1",
                        "source_name": "Alpha.pdf",
                        "source_location": "Drive/Alpha.pdf",
                        "source_url": "https://drive/file-1",
                        "google_drive_version": "8",
                        "google_drive_modified_time": "2026-05-24T00:00:00Z",
                        "page_number": 1,
                    },
                },
            )(),
        ]})()


class VectorSearchTests(unittest.TestCase):
    def test_group_page_results_by_file_sorts_files_and_pages_by_score(self):
        files = group_page_results_by_file(
            [
                PageSearchResult(
                    google_file_id="file-2",
                    source_name="Beta.pdf",
                    source_location="Drive/Beta.pdf",
                    source_url="https://drive/file-2",
                    google_drive_version="3",
                    google_drive_modified_time="2026-05-24T00:00:00Z",
                    page_number=2,
                    score=0.7,
                ),
                PageSearchResult(
                    google_file_id="file-1",
                    source_name="Alpha.pdf",
                    source_location="Drive/Alpha.pdf",
                    source_url="https://drive/file-1",
                    google_drive_version="8",
                    google_drive_modified_time="2026-05-24T00:00:00Z",
                    page_number=1,
                    score=0.8,
                ),
                PageSearchResult(
                    google_file_id="file-1",
                    source_name="Alpha.pdf",
                    source_location="Drive/Alpha.pdf",
                    source_url="https://drive/file-1",
                    google_drive_version="8",
                    google_drive_modified_time="2026-05-24T00:00:00Z",
                    page_number=3,
                    score=0.9,
                ),
            ]
        )

        self.assertEqual([file.google_file_id for file in files], ["file-1", "file-2"])
        self.assertEqual([page.page_number for page in files[0].pages], [3, 1])
        self.assertEqual(files[0].score, 0.9)

    def test_qdrant_search_adapter_returns_grouped_results(self):
        client = FakeQdrantClient()
        adapter = QdrantSearchAdapter(client=client, collection="kbsearch")

        results = adapter.search_pages(vector=[0.1, 0.2], limit=5, min_score=0.5)

        self.assertEqual(client.calls[0]["collection_name"], "kbsearch")
        self.assertEqual(client.calls[0]["query"], [0.1, 0.2])
        self.assertEqual(client.calls[0]["limit"], 5)
        self.assertEqual(client.calls[0]["score_threshold"], 0.5)
        self.assertEqual([file.google_file_id for file in results], ["file-1", "file-2"])

    def test_qdrant_search_adapter_rejects_missing_required_payload(self):
        client = FakeQdrantClient()
        client.query_points = lambda **_: type(
            "Response",
            (),
            {"points": [type("Record", (), {"score": 0.9, "payload": {"page_number": 1}})()]},
        )()

        with self.assertRaisesRegex(ExternalServiceError, "invalid response"):
            QdrantSearchAdapter(client=client, collection="kbsearch").search_pages(
                vector=[0.1, 0.2], limit=5
            )

    def test_qdrant_search_adapter_rejects_inconsistent_file_metadata(self):
        pages = [
            PageSearchResult(
                google_file_id="file-1",
                source_name="Alpha.pdf",
                source_location="Drive/Alpha.pdf",
                source_url="https://drive/file-1",
                google_drive_version="8",
                google_drive_modified_time=modified_time,
                page_number=page_number,
                score=score,
            )
            for page_number, score, modified_time in (
                (1, 0.9, "2026-05-24T00:00:00Z"),
                (2, 0.8, "2026-05-25T00:00:00Z"),
            )
        ]

        with self.assertRaisesRegex(ExternalServiceError, "inconsistent metadata"):
            group_page_results_by_file(pages)

    def test_qdrant_search_adapter_wraps_client_errors(self):
        client = FakeQdrantClient()
        client.query_points = lambda **_: (_ for _ in ()).throw(RuntimeError("connection detail"))

        with self.assertRaisesRegex(ExternalServiceError, "Qdrant vector search failed") as ctx:
            QdrantSearchAdapter(client=client, collection="kbsearch").search_pages(
                vector=[0.1, 0.2], limit=5
            )

        self.assertIsInstance(ctx.exception.__cause__, RuntimeError)


if __name__ == "__main__":
    unittest.main()
