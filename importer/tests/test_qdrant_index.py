import unittest
from unittest.mock import Mock

from app.errors import ExternalServiceError
from app.models import PageVectorMetadata, QdrantDocument
from app.qdrant_index import (
    QdrantIndexAdapter,
    ensure_google_file_id_payload_index,
    ensure_qdrant_collection,
)


class FakeQdrantClient:
    def __init__(self):
        self.deleted = []
        self.upserted = []
        self.scroll_calls = 0

    def scroll(self, **kwargs):
        self.scroll_calls += 1
        if self.scroll_calls == 1:
            return (
                [
                    type("Record", (), {"payload": {"google_file_id": "file-1", "google_drive_version": "7"}})(),
                    type("Record", (), {"payload": {"google_file_id": "file-1", "google_drive_version": "7"}})(),
                ],
                None,
            )
        return ([], None)

    def delete(self, **kwargs):
        self.deleted.append(kwargs)

    def upsert(self, **kwargs):
        self.upserted.append(kwargs)


class QdrantIndexTests(unittest.TestCase):
    def test_list_documents_summarizes_by_google_file_id(self):
        index = QdrantIndexAdapter(client=FakeQdrantClient(), collection="kbsearch")

        self.assertEqual(index.list_documents(), [QdrantDocument(file_id="file-1", version="7")])

    def test_delete_document_deletes_by_google_file_id(self):
        client = FakeQdrantClient()
        index = QdrantIndexAdapter(client=client, collection="kbsearch")

        index.delete_document("file-1")

        self.assertEqual(client.deleted[0]["collection_name"], "kbsearch")

    def test_upsert_page_vectors_writes_points(self):
        client = FakeQdrantClient()
        index = QdrantIndexAdapter(client=client, collection="kbsearch")
        metadata = PageVectorMetadata(
            google_file_id="file-1",
            source_name="Spec.pdf",
            source_location="/Spec.pdf",
            source_url="https://drive/file-1",
            google_drive_version="7",
            google_drive_modified_time="2026-05-24T00:00:00Z",
            page_number=1,
        )

        index.upsert_page_vectors([([0.1, 0.2], metadata)])

        self.assertEqual(client.upserted[0]["collection_name"], "kbsearch")
        self.assertEqual(len(client.upserted[0]["points"]), 1)

    def test_ensure_qdrant_collection_creates_missing_collection(self):
        client = Mock()
        client.collection_exists.return_value = False

        created = ensure_qdrant_collection(client, "kbsearch", 2560)

        self.assertTrue(created)
        client.create_collection.assert_called_once()
        kwargs = client.create_collection.call_args.kwargs
        self.assertEqual(kwargs["collection_name"], "kbsearch")
        self.assertEqual(kwargs["vectors_config"].size, 2560)

    def test_ensure_qdrant_collection_skips_existing_collection(self):
        client = Mock()
        client.collection_exists.return_value = True

        created = ensure_qdrant_collection(client, "kbsearch", 2560)

        self.assertFalse(created)
        client.create_collection.assert_not_called()
        client.create_payload_index.assert_called_once()

    def test_ensure_google_file_id_payload_index_ignores_existing_index(self):
        client = Mock()
        client.create_payload_index.side_effect = RuntimeError("Index already exists")

        ensure_google_file_id_payload_index(client, "kbsearch")

        client.create_payload_index.assert_called_once()

    def test_ensure_qdrant_collection_raises_external_service_error_on_failure(self):
        client = Mock()
        client.collection_exists.return_value = False
        client.create_collection.side_effect = RuntimeError("boom")

        with self.assertRaisesRegex(ExternalServiceError, "create collection failed"):
            ensure_qdrant_collection(client, "kbsearch", 2560)


if __name__ == "__main__":
    unittest.main()
