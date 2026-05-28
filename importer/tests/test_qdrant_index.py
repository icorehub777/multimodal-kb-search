import unittest

from kbsearch_importer.models import PageVectorMetadata, QdrantDocument
from kbsearch_importer.qdrant_index import QdrantIndexAdapter


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


if __name__ == "__main__":
    unittest.main()
