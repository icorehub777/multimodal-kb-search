import json
import tempfile
import unittest
from pathlib import Path

from kbsearch_cli.cli_output import (
    build_query_started_event_payload,
    build_query_success_payload,
    format_progress_message,
)
from kbsearch_cli.models import (
    DownloadedFileResult,
    DownloadFailureResult,
    FullTextSearchResult,
    QueryResultBundle,
    QueryRunResult,
    QueryWarningResult,
)


class CliOutputTests(unittest.TestCase):
    def test_build_query_started_event_payload_points_agent_to_log_monitoring(self):
        payload = build_query_started_event_payload(
            run_id="run12345",
            output_dir=Path("C:/tmp/query/run"),
            log_path=Path("C:/tmp/logs/kbsearch-run12345.log"),
        )

        self.assertEqual(
            payload,
            {
                "event": "query_started",
                "status": "started",
                "run_id": "run12345",
                "output_dir": "C:/tmp/query/run",
                "log_path": "C:/tmp/logs/kbsearch-run12345.log",
                "monitor": "log",
                "stdout": "final_json_on_success",
            },
        )

    def test_format_progress_message_uses_stable_key_value_format(self):
        message = format_progress_message(
            "download",
            {
                "status": "finished",
                "file_id": "file-1",
                "text_page_count": 10,
                "rendered_page_count": 2,
                "index": 2,
                "total": 4,
            },
        )

        self.assertEqual(
            message,
            "Query progress: phase=download status=finished file_id=file-1 "
            "text_page_count=10 rendered_page_count=2 index=2 total=4",
        )

    def test_build_query_success_payload_includes_output_dir_and_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_dir = Path(temp_dir) / "20260531-120000-手動測試"
            bundle_dir.mkdir()
            bundle = QueryResultBundle(
                path=bundle_dir,
                query_plan_path=bundle_dir / "query_plan.json",
                full_text_results_path=bundle_dir / "full_text_results.json",
                vector_results_path=bundle_dir / "vector_results.json",
                downloaded_files_path=bundle_dir / "downloaded_files.json",
                full_text_results=[
                    FullTextSearchResult("file-1", "Alpha.pdf", "application/pdf", "")
                ],
                vector_results=[],
                download_failures_path=bundle_dir / "download_failures.json",
                warnings_path=bundle_dir / "warnings.json",
            )
            result = QueryRunResult(
                bundle=bundle,
                full_text_count=1,
                vector_count=4,
                vector_accessible_count=4,
                union_count=4,
                download_count=3,
                downloaded_files=[
                    DownloadedFileResult(
                        google_file_id="file-1",
                        name="Alpha.pdf",
                        directory=bundle_dir / "Alpha.pdf-abcde",
                        source_path=bundle_dir / "Alpha.pdf-abcde" / "Alpha.pdf",
                        pdf_path=bundle_dir / "Alpha.pdf-abcde" / "pdf" / "document.pdf",
                        text_paths=[
                            bundle_dir / "Alpha.pdf-abcde" / "text" / "0001.txt",
                            bundle_dir / "Alpha.pdf-abcde" / "text" / "0002.txt",
                        ],
                        page_paths=[
                            bundle_dir / "Alpha.pdf-abcde" / "pages" / "0002.png",
                        ],
                    )
                ],
                download_failure_count=1,
                download_failures=[
                    DownloadFailureResult(
                        google_file_id="file-4",
                        name="Broken.pdf",
                        stage="process",
                        error_type="DocumentRenderError",
                        message="invalid PDF",
                        google_drive_url="https://drive/file-4",
                        vector_page_numbers=[3, 5],
                        full_text_query="fullText contains 'broken'",
                    )
                ],
                warning_count=1,
                warnings=[
                    QueryWarningResult(
                        code="vector_pages_unrendered",
                        google_file_id="file-5",
                        name="Archive.zip",
                        mime_type="application/zip",
                        google_drive_url="https://drive/file-5",
                        vector_page_numbers=[7],
                        message=(
                            "Vector search matched pages, but no page images were "
                            "rendered for this file."
                        ),
                    )
                ],
            )

            payload = build_query_success_payload(
                result,
                run_id="run12345",
                log_path=Path("C:/tmp/logs/kbsearch-run12345.log"),
            )

        self.assertEqual(
            payload,
            {
                "status": "finished_with_errors",
                "run_id": "run12345",
                "log_path": "C:/tmp/logs/kbsearch-run12345.log",
                "output_dir": bundle_dir.as_posix(),
                "full_text_count": 1,
                "vector_count": 4,
                "download_count": 3,
                "downloaded_files_path": (
                    bundle_dir / "downloaded_files.json"
                ).as_posix(),
                "downloaded_files": [
                    {
                        "google_file_id": "file-1",
                        "name": "Alpha.pdf",
                        "directory": (bundle_dir / "Alpha.pdf-abcde").as_posix(),
                        "source_path": (
                            bundle_dir / "Alpha.pdf-abcde" / "Alpha.pdf"
                        ).as_posix(),
                        "pdf_path": (
                            bundle_dir / "Alpha.pdf-abcde" / "pdf" / "document.pdf"
                        ).as_posix(),
                        "text_paths": [
                            (
                                bundle_dir
                                / "Alpha.pdf-abcde"
                                / "text"
                                / "0001.txt"
                            ).as_posix(),
                            (
                                bundle_dir
                                / "Alpha.pdf-abcde"
                                / "text"
                                / "0002.txt"
                            ).as_posix(),
                        ],
                        "page_paths": [
                            (
                                bundle_dir
                                / "Alpha.pdf-abcde"
                                / "pages"
                                / "0002.png"
                            ).as_posix(),
                        ],
                    }
                ],
                "download_failure_count": 1,
                "download_failures_path": (
                    bundle_dir / "download_failures.json"
                ).as_posix(),
                "warning_count": 1,
                "warnings_path": (bundle_dir / "warnings.json").as_posix(),
                "download_failures": [
                    {
                        "google_file_id": "file-4",
                        "name": "Broken.pdf",
                        "stage": "process",
                        "error_type": "DocumentRenderError",
                        "message": "invalid PDF",
                        "google_drive_url": "https://drive/file-4",
                        "vector_page_numbers": [3, 5],
                        "full_text_query": "fullText contains 'broken'",
                    }
                ],
                "warnings": [
                    {
                        "code": "vector_pages_unrendered",
                        "google_file_id": "file-5",
                        "name": "Archive.zip",
                        "mime_type": "application/zip",
                        "google_drive_url": "https://drive/file-5",
                        "vector_page_numbers": [7],
                        "message": (
                            "Vector search matched pages, but no page images were "
                            "rendered for this file."
                        ),
                    }
                ],
            },
        )
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
