import tempfile
import unittest
from pathlib import Path

from kbsearch_cli.models import FullTextSearchResult, PageSearchResult, VectorFileSearchResult
from kbsearch_cli.errors import QueryCliError
from kbsearch_cli.orchestrator import QueryOrchestrator
from kbsearch_cli.output import QueryResultWriter
from kbsearch_cli.google_drive import safe_download_name


class FakeGoogleDriveClient:
    def __init__(self):
        self.downloads = []
        self.metadata_resolves = []
        self.drive_queries = []

    def search(self, drive_query, limit):
        self.drive_queries.append(drive_query)
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

    def resolve_accessible_metadata(self, file_ids):
        self.metadata_resolves.append(list(file_ids))
        return {
            file_id: self.get_file_metadata(file_id)
            for file_id in file_ids
            if file_id != "file-3"
        }

    def get_file_metadata(self, file_id):
        names = {
            "file-3": "Gamma.pdf",
            "file-9": "Z.pdf",
        }
        return FullTextSearchResult(
            google_file_id=file_id,
            name=names.get(file_id, f"{file_id}.pdf"),
            mime_type="application/pdf",
            web_url=f"https://drive/{file_id}",
        )

    def download(self, file_id, name, mime_type, output_dir):
        self.downloads.append((file_id, output_dir.name))
        output_path = output_dir / safe_download_name(name)
        output_path.write_bytes(b"pdf")
        return output_path


class FakeBackendClient:
    def __init__(self):
        self.calls = []

    def search(self, query, image_paths, limit, min_score):
        self.calls.append((query, image_paths, limit, min_score))
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
        output_path = output_dir / "0001.png"
        output_path.write_bytes(b"png")
        return [output_path]


def _create_output_dir(root: str, name: str) -> Path:
    output_dir = Path(root) / name
    output_dir.mkdir()
    return output_dir


class QueryOrchestratorTests(unittest.TestCase):
    def test_run_downloads_without_rendering_when_page_renderer_is_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            google_drive = FakeGoogleDriveClient()
            orchestrator = QueryOrchestrator(
                google_drive=google_drive,
                backend=FakeBackendClient(),
                result_writer=QueryResultWriter(),
                page_renderer=None,
            )

            result = orchestrator.run(
                output_dir=_create_output_dir(temp_dir, "僅下載"),
                vector_query="semantic alpha",
                drive_query="fullText contains 'alpha' and trashed = false",
                limit=10,
                min_score=0.5,
            )

            alpha = result.bundle.path / "Alpha.pdf-file-1"
            beta = result.bundle.path / "Beta.pdf-file-2"
            self.assertTrue((alpha / "Alpha.pdf").exists())
            self.assertTrue((beta / "Beta.pdf").exists())
            self.assertEqual(list(alpha.glob("*.png")), [])
            self.assertEqual(list(beta.glob("*.png")), [])
            self.assertEqual(result.downloaded_files[0].page_paths, [])

    def test_run_downloads_and_renders_union_of_full_text_and_vector_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            google_drive = FakeGoogleDriveClient()
            backend = FakeBackendClient()
            renderer = FakePageRenderer()
            orchestrator = QueryOrchestrator(
                google_drive=google_drive,
                backend=backend,
                result_writer=QueryResultWriter(),
                page_renderer=renderer,
            )

            image_path = Path(temp_dir) / "sample.png"
            image_path.write_bytes(b"png")
            result = orchestrator.run(
                output_dir=_create_output_dir(temp_dir, "客戶查詢"),
                vector_query="semantic alpha",
                drive_query="fullText contains 'alpha' and trashed = false",
                limit=10,
                min_score=0.5,
                image_paths=[image_path],
            )
            bundle = result.bundle

            file_dir = bundle.path / "Alpha.pdf-file-1"
            beta_dir = bundle.path / "Beta.pdf-file-2"
            self.assertTrue((file_dir / "Alpha.pdf").exists())
            self.assertTrue((file_dir / "0001.png").exists())
            self.assertTrue((beta_dir / "Beta.pdf").exists())
            self.assertFalse((bundle.path / "Gamma.pdf-file-3").exists())
            self.assertEqual(
                google_drive.downloads,
                [("file-1", "Alpha.pdf-file-1"), ("file-2", "Beta.pdf-file-2")],
            )
            self.assertEqual(google_drive.drive_queries, ["fullText contains 'alpha' and trashed = false"])
            self.assertEqual(backend.calls, [("semantic alpha", [image_path], 10, 0.5)])
            self.assertEqual(bundle.query_plan_path.read_text(encoding="utf-8").count(image_path.as_posix()), 1)
            self.assertEqual(renderer.rendered, ["Alpha.pdf", "Beta.pdf"])

    def test_run_keeps_spreadsheets_without_page_rendering(self):
        class SpreadsheetGoogleDriveClient(FakeGoogleDriveClient):
            def search(self, drive_query, limit):
                return [
                    FullTextSearchResult(
                        google_file_id="sheet-1",
                        name="Orders",
                        mime_type="application/vnd.google-apps.spreadsheet",
                        web_url="https://drive/sheet-1",
                    )
                ]

            def download(self, file_id, name, mime_type, output_dir):
                if mime_type != "application/vnd.google-apps.spreadsheet":
                    return super().download(file_id, name, mime_type, output_dir)
                output_path = output_dir / "Orders.xlsx"
                output_path.write_bytes(b"xlsx")
                return output_path

        with tempfile.TemporaryDirectory() as temp_dir:
            renderer = FakePageRenderer()
            orchestrator = QueryOrchestrator(
                google_drive=SpreadsheetGoogleDriveClient(),
                backend=FakeBackendClient(),
                result_writer=QueryResultWriter(),
                page_renderer=renderer,
            )

            result = orchestrator.run(
                output_dir=_create_output_dir(temp_dir, "試算表"),
                vector_query="orders",
                drive_query="fullText contains 'orders' and trashed = false",
                limit=10,
                min_score=0.5,
            )

            self.assertTrue((result.bundle.path / "Orders-sheet-1" / "Orders.xlsx").exists())
            self.assertEqual(result.downloaded_files[0].page_paths, [])
            self.assertEqual(renderer.rendered, ["file-1.pdf"])

    def test_run_uses_file_id_suffix_when_normalized_file_names_collide(self):
        class CollidingGoogleDriveClient(FakeGoogleDriveClient):
            def search(self, drive_query, limit):
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
                result_writer=QueryResultWriter(),
                page_renderer=FakePageRenderer(),
            )

            result = orchestrator.run(
                output_dir=_create_output_dir(temp_dir, "碰撞"),
                vector_query="alpha",
                drive_query="fullText contains 'alpha' and trashed = false",
                limit=10,
                min_score=0.5,
            )
            bundle = result.bundle

            self.assertTrue((bundle.path / "A_.pdf-file-1").exists())
            self.assertTrue((bundle.path / "A_.pdf-file-2").exists())
            self.assertEqual([download[1] for download in google_drive.downloads], ["A_.pdf-file-1", "A_.pdf-file-2"])

    def test_run_resolves_vector_metadata_in_one_batch(self):
        class ThreeResultBackendClient:
            def search(self, query, image_paths, limit, min_score):
                return [
                    VectorFileSearchResult("file-1", "A.pdf", "", "", "1", "", 0.9, []),
                    VectorFileSearchResult("file-2", "B.pdf", "", "", "1", "", 0.8, []),
                    VectorFileSearchResult("file-3", "C.pdf", "", "", "1", "", 0.7, []),
                ]

        with tempfile.TemporaryDirectory() as temp_dir:
            google_drive = FakeGoogleDriveClient()
            orchestrator = QueryOrchestrator(
                google_drive=google_drive,
                backend=ThreeResultBackendClient(),
                result_writer=QueryResultWriter(),
                page_renderer=FakePageRenderer(),
            )

            orchestrator.run(
                output_dir=_create_output_dir(temp_dir, "存取檢查"),
                vector_query="alpha",
                drive_query="fullText contains 'alpha' and trashed = false",
                limit=10,
                min_score=0.5,
            )

        self.assertEqual(google_drive.metadata_resolves, [["file-1", "file-2", "file-3"]])

    def test_run_still_downloads_full_text_when_all_vector_results_inaccessible(self):
        class InaccessibleGoogleDriveClient(FakeGoogleDriveClient):
            def resolve_accessible_metadata(self, file_ids):
                self.metadata_resolves.append(list(file_ids))
                return {}

        with tempfile.TemporaryDirectory() as temp_dir:
            google_drive = InaccessibleGoogleDriveClient()
            orchestrator = QueryOrchestrator(
                google_drive=google_drive,
                backend=FakeBackendClient(),
                result_writer=QueryResultWriter(),
                page_renderer=FakePageRenderer(),
            )

            bundle = orchestrator.run(
                output_dir=_create_output_dir(temp_dir, "無存取"),
                vector_query="alpha",
                drive_query="fullText contains 'alpha' and trashed = false",
                limit=10,
                min_score=0.5,
            ).bundle

            self.assertTrue((bundle.path / "Alpha.pdf-file-1").exists())
            self.assertTrue((bundle.path / "Beta.pdf-file-2").exists())
            self.assertEqual(
                google_drive.downloads,
                [("file-1", "Alpha.pdf-file-1"), ("file-2", "Beta.pdf-file-2")],
            )

    def test_run_downloads_vector_only_files_not_in_full_text_results(self):
        class AccessibleOnlyBackendClient:
            def search(self, query, image_paths, limit, min_score):
                return [
                    VectorFileSearchResult("file-9", "Z.pdf", "", "", "1", "", 0.9, []),
                ]

        with tempfile.TemporaryDirectory() as temp_dir:
            google_drive = FakeGoogleDriveClient()
            orchestrator = QueryOrchestrator(
                google_drive=google_drive,
                backend=AccessibleOnlyBackendClient(),
                result_writer=QueryResultWriter(),
                page_renderer=FakePageRenderer(),
            )

            bundle = orchestrator.run(
                output_dir=_create_output_dir(temp_dir, "向量聯集"),
                vector_query="alpha",
                drive_query="fullText contains 'alpha' and trashed = false",
                limit=10,
                min_score=0.5,
            ).bundle

            self.assertTrue((bundle.path / "Alpha.pdf-file-1").exists())
            self.assertTrue((bundle.path / "Beta.pdf-file-2").exists())
            self.assertTrue((bundle.path / "Z.pdf-file-9").exists())
            self.assertEqual(len(google_drive.downloads), 3)

    def test_run_rejects_missing_image_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator = QueryOrchestrator(
                google_drive=FakeGoogleDriveClient(),
                backend=FakeBackendClient(),
                result_writer=QueryResultWriter(),
                page_renderer=FakePageRenderer(),
            )

            with self.assertRaisesRegex(QueryCliError, "Query image not found"):
                orchestrator.run(
                    output_dir=_create_output_dir(temp_dir, "缺圖"),
                    vector_query="alpha",
                    drive_query="fullText contains 'alpha' and trashed = false",
                    limit=10,
                    min_score=0.5,
                    image_paths=[Path("C:/missing/sample.png")],
                )


if __name__ == "__main__":
    unittest.main()
