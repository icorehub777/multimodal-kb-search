import tempfile
import threading
import unittest
from pathlib import Path

from kbsearch_cli.models import FullTextSearchResult, PageSearchResult, VectorFileSearchResult
from kbsearch_cli.orchestrator import QueryOrchestrator
from kbsearch_cli.output import QueryResultWriter
from kbsearch_cli.google_drive import safe_download_name


class FakeGoogleDriveClient:
    def __init__(self):
        self.downloads = []
        self.access_checks = []

    def search_full_text(self, query, limit):
        return [
            FullTextSearchResult(
                google_file_id="file-1",
                name="Alpha.pdf",
                mime_type="application/pdf",
                web_url="https://drive/file-1",
            ),
            FullTextSearchResult(
                google_file_id="file-2",
                name="Beta.pdf",
                mime_type="application/pdf",
                web_url="https://drive/file-2",
            ),
        ]

    def can_access(self, file_id):
        self.access_checks.append(file_id)
        return file_id != "file-3"

    def download(self, file_id, name, mime_type, output_dir):
        self.downloads.append((file_id, output_dir.name))
        output_path = output_dir / safe_download_name(name)
        output_path.write_bytes(b"pdf")
        return output_path


class FakeBackendClient:
    def search(self, query, image_paths, limit, min_score):
        return [
            VectorFileSearchResult(
                google_file_id="file-1",
                source_name="Alpha.pdf",
                source_location="Drive/Alpha.pdf",
                source_url="https://drive/file-1",
                google_drive_version="7",
                google_drive_modified_time="2026-05-24T00:00:00Z",
                score=0.91,
                pages=[
                    PageSearchResult(
                        page_number=2,
                        page_image_path="pages/alpha/02.png",
                        source_file_path="source/Alpha.pdf",
                        score=0.91,
                    )
                ],
            ),
            VectorFileSearchResult(
                google_file_id="file-3",
                source_name="Gamma.pdf",
                source_location="Drive/Gamma.pdf",
                source_url="https://drive/file-3",
                google_drive_version="4",
                google_drive_modified_time="2026-05-24T00:00:00Z",
                score=0.8,
                pages=[],
            ),
        ]


class FakePageRenderer:
    def __init__(self):
        self.rendered = []

    def render_pages(self, source_path, output_dir):
        self.rendered.append(source_path.name)
        output_path = output_dir / "01.png"
        output_path.write_bytes(b"png")
        return [output_path]


class QueryOrchestratorTests(unittest.TestCase):
    def test_run_downloads_and_renders_only_intersection_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            google_drive = FakeGoogleDriveClient()
            renderer = FakePageRenderer()
            orchestrator = QueryOrchestrator(
                google_drive=google_drive,
                backend=FakeBackendClient(),
                result_writer=QueryResultWriter(Path(temp_dir), clock=lambda: "20260524-203000"),
                page_renderer=renderer,
            )

            bundle = orchestrator.run(query_name="客戶查詢", query="alpha", limit=10, min_score=0.5)

            file_dir = bundle.path / "Alpha.pdf-file-1"
            self.assertTrue((file_dir / "Alpha.pdf").exists())
            self.assertTrue((file_dir / "01.png").exists())
            self.assertFalse((bundle.path / "Beta.pdf").exists())
            self.assertEqual(google_drive.downloads, [("file-1", "Alpha.pdf-file-1")])
            self.assertEqual(renderer.rendered, ["Alpha.pdf"])

    def test_run_uses_file_id_suffix_when_normalized_file_names_collide(self):
        class CollidingGoogleDriveClient(FakeGoogleDriveClient):
            def search_full_text(self, query, limit):
                return [
                    FullTextSearchResult("file-1", "A?.pdf", "application/pdf", "https://drive/file-1"),
                    FullTextSearchResult("file-2", "A:.pdf", "application/pdf", "https://drive/file-2"),
                ]

        class CollidingBackendClient:
            def search(self, query, image_paths, limit, min_score):
                return [
                    VectorFileSearchResult("file-1", "A?.pdf", "", "", "1", "", 0.9, []),
                    VectorFileSearchResult("file-2", "A:.pdf", "", "", "1", "", 0.8, []),
                ]

        with tempfile.TemporaryDirectory() as temp_dir:
            google_drive = CollidingGoogleDriveClient()
            orchestrator = QueryOrchestrator(
                google_drive=google_drive,
                backend=CollidingBackendClient(),
                result_writer=QueryResultWriter(Path(temp_dir), clock=lambda: "20260524-203000"),
                page_renderer=FakePageRenderer(),
            )

            bundle = orchestrator.run(query_name="碰撞", query="alpha", limit=10, min_score=0.5)

            self.assertTrue((bundle.path / "A_.pdf-file-1").exists())
            self.assertTrue((bundle.path / "A_.pdf-file-2").exists())
            self.assertEqual([download[1] for download in google_drive.downloads], ["A_.pdf-file-1", "A_.pdf-file-2"])

    def test_run_checks_vector_access_in_parallel(self):
        class ConcurrentGoogleDriveClient(FakeGoogleDriveClient):
            def __init__(self):
                super().__init__()
                self._barrier = threading.Barrier(3, timeout=2)
                self._lock = threading.Lock()
                self._active = 0
                self.max_active = 0

            def search_full_text(self, query, limit):
                return [
                    FullTextSearchResult("file-1", "A.pdf", "application/pdf", "https://drive/file-1"),
                    FullTextSearchResult("file-2", "B.pdf", "application/pdf", "https://drive/file-2"),
                    FullTextSearchResult("file-3", "C.pdf", "application/pdf", "https://drive/file-3"),
                ]

            def can_access(self, file_id):
                with self._lock:
                    self._active += 1
                    self.max_active = max(self.max_active, self._active)
                try:
                    self._barrier.wait()
                    return True
                finally:
                    with self._lock:
                        self._active -= 1

        class ThreeResultBackendClient:
            def search(self, query, image_paths, limit, min_score):
                return [
                    VectorFileSearchResult("file-1", "A.pdf", "", "", "1", "", 0.9, []),
                    VectorFileSearchResult("file-2", "B.pdf", "", "", "1", "", 0.8, []),
                    VectorFileSearchResult("file-3", "C.pdf", "", "", "1", "", 0.7, []),
                ]

        with tempfile.TemporaryDirectory() as temp_dir:
            google_drive = ConcurrentGoogleDriveClient()
            orchestrator = QueryOrchestrator(
                google_drive=google_drive,
                backend=ThreeResultBackendClient(),
                result_writer=QueryResultWriter(Path(temp_dir), clock=lambda: "20260524-203000"),
                page_renderer=FakePageRenderer(),
            )

            orchestrator.run(query_name="並行", query="alpha", limit=10, min_score=0.5)

        self.assertGreater(google_drive.max_active, 1)


if __name__ == "__main__":
    unittest.main()
