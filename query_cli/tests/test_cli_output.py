import json
import tempfile
import unittest
from pathlib import Path

from kbsearch_cli.cli_output import build_query_success_payload, format_progress_message
from kbsearch_cli.models import (
    FullTextSearchResult,
    QueryResultBundle,
    QueryRunResult,
)


class CliOutputTests(unittest.TestCase):
    def test_format_progress_message_uses_stable_key_value_format(self):
        message = format_progress_message(
            "download",
            {
                "status": "finished",
                "file_id": "file-1",
                "page_count": 10,
                "index": 2,
                "total": 4,
            },
        )

        self.assertEqual(
            message,
            "Query progress: phase=download status=finished file_id=file-1 page_count=10 index=2 total=4",
        )

    def test_build_query_success_payload_includes_bundle_name_and_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_dir = Path(temp_dir) / "20260531-120000-手動測試"
            bundle_dir.mkdir()
            bundle = QueryResultBundle(
                path=bundle_dir,
                query_plan_path=bundle_dir / "query_plan.json",
                full_text_results_path=bundle_dir / "full_text_results.json",
                vector_results_path=bundle_dir / "vector_results.json",
                full_text_results=[
                    FullTextSearchResult("file-1", "Alpha.pdf", "application/pdf", "")
                ],
                vector_results=[],
            )
            result = QueryRunResult(
                query_name="手動測試",
                bundle=bundle,
                full_text_count=1,
                vector_count=4,
                vector_accessible_count=4,
                union_count=4,
                download_count=3,
                downloaded_files=[],
            )

            payload = build_query_success_payload(result)

        self.assertEqual(
            payload,
            {
                "status": "finished",
                "bundle_name": "20260531-120000-手動測試",
                "full_text_count": 1,
                "vector_count": 4,
                "download_count": 3,
            },
        )
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
