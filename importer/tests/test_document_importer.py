import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.document_importer import PageImage, PipelineDocumentImporter
from app.errors import DocumentImportError
from app.models import WorkspaceDocument


class FakeDownloader:
    def download(self, file_id, name, mime_type, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / name
        output_path.write_text("source", encoding="utf-8")
        return output_path


class FakeConverter:
    def convert_to_pdf(self, source_path, mime_type, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "source.pdf"
        output_path.write_text("pdf", encoding="utf-8")
        return output_path


class FakeRenderer:
    def render_pages(self, pdf_path, output_dir):
        return [
            PageImage(page_number=1, path=output_dir / "0001.png"),
            PageImage(page_number=2, path=output_dir / "0002.png"),
        ]


class RoutingRenderer:
    def render_pages(self, source_path, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "0001.png"
        output_path.write_text(source_path.suffix, encoding="utf-8")
        return [PageImage(page_number=1, path=output_path)]


class FakeEmbedder:
    def __init__(self, fail_on_page_name=None):
        self.fail_on_page_name = fail_on_page_name

    def embed_page_image(self, image_path):
        if image_path.name == self.fail_on_page_name:
            raise RuntimeError("embedding failed")
        return [float(image_path.stem), 0.0]


class FakeQdrantIndex:
    def __init__(self):
        self.pages = []

    def upsert_page_vectors(self, pages):
        self.pages.extend(pages)
        return len(pages)


class DocumentImporterTests(unittest.TestCase):
    def test_import_document_upserts_each_page_with_metadata(self):
        document = WorkspaceDocument(
            file_id="file-1",
            name="Spec.pdf",
            location="/Spec.pdf",
            web_url="https://drive/file-1",
            version="7",
            modified_time="2026-05-24T00:00:00Z",
            mime_type="application/pdf",
        )
        qdrant_index = FakeQdrantIndex()

        with TemporaryDirectory() as temp_dir:
            importer = PipelineDocumentImporter(
                downloader=FakeDownloader(),
                converter=FakeConverter(),
                renderer=FakeRenderer(),
                embedder=FakeEmbedder(),
                qdrant_index=qdrant_index,
                work_dir=Path(temp_dir),
            )

            imported_pages = importer.import_document(document)

        self.assertEqual(imported_pages, 2)
        self.assertEqual(len(qdrant_index.pages), 2)
        self.assertEqual(qdrant_index.pages[0][0], [1.0, 0.0])
        self.assertEqual(qdrant_index.pages[0][1].google_file_id, "file-1")
        self.assertEqual(qdrant_index.pages[1][1].page_number, 2)

    def test_import_document_does_not_upsert_partial_vectors_when_embedding_fails(self):
        document = WorkspaceDocument(
            file_id="file-1",
            name="Spec.pdf",
            location="/Spec.pdf",
            web_url="https://drive/file-1",
            version="7",
            modified_time="2026-05-24T00:00:00Z",
            mime_type="application/pdf",
        )
        qdrant_index = FakeQdrantIndex()

        with TemporaryDirectory() as temp_dir:
            importer = PipelineDocumentImporter(
                downloader=FakeDownloader(),
                converter=FakeConverter(),
                renderer=FakeRenderer(),
                embedder=FakeEmbedder(fail_on_page_name="0002.png"),
                qdrant_index=qdrant_index,
                work_dir=Path(temp_dir),
            )

            with self.assertRaises(DocumentImportError):
                importer.import_document(document)

        self.assertEqual(qdrant_index.pages, [])

    def test_import_document_removes_work_dir_after_success_when_configured(self):
        document = WorkspaceDocument(
            file_id="file-1",
            name="Spec.pdf",
            location="/Spec.pdf",
            web_url="https://drive/file-1",
            version="7",
            modified_time="2026-05-24T00:00:00Z",
            mime_type="application/pdf",
        )

        with TemporaryDirectory() as temp_dir:
            work_dir = Path(temp_dir) / "work"
            importer = PipelineDocumentImporter(
                downloader=FakeDownloader(),
                converter=FakeConverter(),
                renderer=FakeRenderer(),
                embedder=FakeEmbedder(),
                qdrant_index=FakeQdrantIndex(),
                work_dir=work_dir,
                keep_success_work_files=False,
            )

            importer.import_document(document)

            self.assertFalse((work_dir / "file-1").exists())

    def test_import_document_keeps_work_dir_after_failure_when_configured(self):
        document = WorkspaceDocument(
            file_id="file-1",
            name="Spec.pdf",
            location="/Spec.pdf",
            web_url="https://drive/file-1",
            version="7",
            modified_time="2026-05-24T00:00:00Z",
            mime_type="application/pdf",
        )

        with TemporaryDirectory() as temp_dir:
            work_dir = Path(temp_dir) / "work"
            importer = PipelineDocumentImporter(
                downloader=FakeDownloader(),
                converter=FakeConverter(),
                renderer=FakeRenderer(),
                embedder=FakeEmbedder(fail_on_page_name="0002.png"),
                qdrant_index=FakeQdrantIndex(),
                work_dir=work_dir,
                keep_failed_work_files=True,
            )

            with self.assertRaises(DocumentImportError):
                importer.import_document(document)

            self.assertTrue((work_dir / "file-1").exists())

    def test_import_image_document_uses_single_page_image_pipeline(self):
        document = WorkspaceDocument(
            file_id="image-1",
            name="photo.jpg",
            location="/photo.jpg",
            web_url="https://drive/image-1",
            version="7",
            modified_time="2026-05-24T00:00:00Z",
            mime_type="image/jpeg",
        )
        qdrant_index = FakeQdrantIndex()

        with TemporaryDirectory() as temp_dir:
            importer = PipelineDocumentImporter(
                downloader=FakeDownloader(),
                converter=FakeConverter(),
                renderer=RoutingRenderer(),
                embedder=FakeEmbedder(),
                qdrant_index=qdrant_index,
                work_dir=Path(temp_dir),
            )

            imported_pages = importer.import_document(document)

        self.assertEqual(imported_pages, 1)
        self.assertEqual(qdrant_index.pages[0][1].page_number, 1)


if __name__ == "__main__":
    unittest.main()
