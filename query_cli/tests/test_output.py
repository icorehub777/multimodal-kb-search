import json
import tempfile
import unittest
from pathlib import Path

from kbsearch_cli.models import (
    FullTextPageSearchResult,
    FullTextSearchResult,
    PageSearchResult,
    VectorFileSearchResult,
)
from kbsearch_cli.output import QueryResultWriter, safe_path_name


class QueryOutputTests(unittest.TestCase):
    def test_safe_path_name_removes_path_traversal_and_invalid_characters(self):
        self.assertEqual(safe_path_name("../客戶:A?"), "客戶_A")
        self.assertEqual(safe_path_name(""), "untitled")

    def test_query_result_writer_writes_result_lists_to_output_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            writer = QueryResultWriter()
            output_dir = Path(temp_dir) / "20260524-203000-測試查詢"
            output_dir.mkdir()

            bundle = writer.create_bundle(
                output_dir=output_dir,
                query_plan={
                    "vector_query": "semantic spec",
                    "drive_query": "fullText contains 'spec' and trashed = false",
                    "image_paths": ["sample.png"],
                    "limit": 5,
                    "min_score": 0.4,
                },
                full_text_results=[
                    FullTextSearchResult(
                        google_file_id="file-1",
                        name="Spec.pdf",
                        mime_type="application/pdf",
                        web_url="https://drive/file-1",
                        source_location="Drive/Spec.pdf",
                        pages=[FullTextPageSearchResult(page_number=2, keyword="spec")],
                    )
                ],
                vector_results=[
                    VectorFileSearchResult(
                        google_file_id="file-1",
                        source_name="Spec.pdf",
                        source_location="Drive/Spec.pdf",
                        source_url="https://drive/file-1",
                        google_drive_version="7",
                        google_drive_modified_time="2026-05-24T00:00:00Z",
                        score=0.9,
                        pages=[
                            PageSearchResult(
                                page_number=1,
                                score=0.9,
                            )
                        ],
                    )
                ],
            )

            self.assertEqual(bundle.path, output_dir)
            full_text_json = json.loads((bundle.path / "full_text_results.json").read_text(encoding="utf-8"))
            vector_json = json.loads((bundle.path / "vector_results.json").read_text(encoding="utf-8"))
            query_plan_json = json.loads((bundle.path / "query_plan.json").read_text(encoding="utf-8"))
            warnings_json = json.loads((bundle.path / "warnings.json").read_text(encoding="utf-8"))

        self.assertEqual(full_text_json[0]["google_file_id"], "file-1")
        self.assertEqual(full_text_json[0]["source_location"], "Drive/Spec.pdf")
        self.assertEqual(
            full_text_json[0]["pages"],
            [{"page_number": 2, "keyword": "spec"}],
        )
        self.assertEqual(vector_json[0]["pages"][0]["page_number"], 1)
        self.assertEqual(query_plan_json["drive_query"], "fullText contains 'spec' and trashed = false")
        self.assertEqual(warnings_json, [])

    def test_reserve_output_directory_creates_parents_and_rejects_existing_directory(self):
        from kbsearch_cli.errors import QueryCliError
        from kbsearch_cli.output import reserve_output_directory

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "task" / "query_results" / "query-01"

            reserve_output_directory(output_dir)

            self.assertTrue(output_dir.is_dir())
            with self.assertRaisesRegex(QueryCliError, "already exists"):
                reserve_output_directory(output_dir)


if __name__ == "__main__":
    unittest.main()
