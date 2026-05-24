import json
import tempfile
import unittest
from pathlib import Path

from kbsearch_cli.models import FullTextSearchResult, PageSearchResult, VectorFileSearchResult
from kbsearch_cli.output import QueryResultWriter, safe_path_name


class QueryOutputTests(unittest.TestCase):
    def test_safe_path_name_removes_path_traversal_and_invalid_characters(self):
        self.assertEqual(safe_path_name("../客戶:A?"), "客戶_A")
        self.assertEqual(safe_path_name(""), "untitled")

    def test_query_result_writer_creates_query_folder_and_result_lists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            writer = QueryResultWriter(
                results_root=Path(temp_dir),
                clock=lambda: "20260524-203000",
            )

            bundle = writer.create_bundle(
                query_name="../測試查詢",
                full_text_results=[
                    FullTextSearchResult(
                        google_file_id="file-1",
                        name="Spec.pdf",
                        mime_type="application/pdf",
                        web_url="https://drive/file-1",
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
                                page_image_path="pages/01.png",
                                source_file_path="source/Spec.pdf",
                                score=0.9,
                            )
                        ],
                    )
                ],
            )

            self.assertEqual(bundle.path.name, "20260524-203000-測試查詢")
            full_text_json = json.loads((bundle.path / "full_text_results.json").read_text(encoding="utf-8"))
            vector_json = json.loads((bundle.path / "vector_results.json").read_text(encoding="utf-8"))

        self.assertEqual(full_text_json[0]["google_file_id"], "file-1")
        self.assertEqual(vector_json[0]["pages"][0]["page_number"], 1)


if __name__ == "__main__":
    unittest.main()
