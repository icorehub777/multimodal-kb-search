import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kbsearch_cli.models import (
    FullTextPageSearchResult,
    FullTextSearchResult,
    PageSearchResult,
    VectorFileSearchResult,
)
from kbsearch_cli.output import QueryResultWriter, safe_path_name


class QueryOutputTests(unittest.TestCase):
    def test_query_paths_recheck_task_root_link_boundary(self):
        from kbsearch_cli.errors import QueryInputError
        from kbsearch_cli.output import resolve_query_image_paths, resolve_query_output_directory

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir).resolve() / "workspace"
            root = workspace / "tasks"
            original_resolve = Path.resolve
            with patch.object(Path, "resolve", autospec=True, side_effect=lambda path: Path(temp_dir).resolve() / "outside" if path == root else original_resolve(path)):
                with self.assertRaisesRegex(QueryInputError, "within the workspace"):
                    resolve_query_output_directory(root, "task", "query")
                with self.assertRaisesRegex(QueryInputError, "within the workspace"):
                    resolve_query_image_paths(root, "task", ["photo.png"])

    def test_query_images_are_read_from_task_directory(self):
        from kbsearch_cli.output import resolve_query_image_paths

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve() / "tasks"
            task = root / "task"
            task.mkdir(parents=True)
            images = [task / "photo.png", task / "圖片.jpg"]
            for image in images:
                image.write_bytes(b"image")
            self.assertEqual(resolve_query_image_paths(root, "task", [p.name for p in images]), images)

    def test_query_images_reject_paths_missing_files_and_directories(self):
        from kbsearch_cli.errors import QueryInputError
        from kbsearch_cli.output import resolve_query_image_paths

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            (root / "task" / "folder.png").mkdir(parents=True)
            for name in ("../photo.png", "nested/photo.png", "nested\\photo.png", "C:\\photo.png", "/photo.png", "", "missing.png", "folder.png"):
                with self.subTest(name=name), self.assertRaises(QueryInputError):
                    resolve_query_image_paths(root, "task", [name])

    def test_query_images_reject_link_outside_task(self):
        from kbsearch_cli.errors import QueryInputError
        from kbsearch_cli.output import resolve_query_image_paths

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            image = root / "task" / "photo.png"
            original_resolve = Path.resolve
            with patch.object(Path, "resolve", autospec=True, side_effect=lambda path: root / "outside.png" if path == image else original_resolve(path)):
                with self.assertRaisesRegex(QueryInputError, "within the task directory"):
                    resolve_query_image_paths(root, "task", ["photo.png"])

    def test_task_output_rejects_link_resolving_outside_root(self):
        from kbsearch_cli.errors import QueryInputError
        from kbsearch_cli.output import resolve_query_output_directory

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve() / "tasks"
            output = root / "task" / "query_results" / "query"
            original_resolve = Path.resolve
            with patch.object(Path, "resolve", autospec=True, side_effect=lambda path: Path(temp_dir).resolve() / "outside" if path == output else original_resolve(path)):
                with self.assertRaisesRegex(QueryInputError, "within the task root"):
                    resolve_query_output_directory(root, "task", "query")
            self.assertFalse(output.exists())

    def test_created_task_results_are_discovered_by_viewer(self):
        from kbsearch_cli.output import resolve_query_output_directory, reserve_output_directory
        from kbsearch_cli.viewer_app import discover_query_results

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve() / "tasks"
            for query in ("first", "second"):
                output = resolve_query_output_directory(root, "task", query)
                reserve_output_directory(output)
                QueryResultWriter().create_bundle(output, {}, [], [])
            results = discover_query_results(root)
            self.assertEqual({item.query_name for item in results}, {"first", "second"})
            self.assertTrue(all(item.task_name == "task" for item in results))

    def test_task_output_uses_configured_root_without_creating_directories(self):
        from kbsearch_cli.output import resolve_query_output_directory

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve() / "tasks"
            output = resolve_query_output_directory(root, "任務", "搜尋")
            self.assertEqual(output, root / "任務" / "query_results" / "搜尋")
            self.assertFalse(root.exists())

    def test_task_output_rejects_invalid_names_and_existing_results(self):
        from kbsearch_cli.errors import QueryInputError
        from kbsearch_cli.output import resolve_query_output_directory

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            for name in ("", " ", ".", "..", "../x", "x/y", "x\\y", "C:x", "CON", "nul.txt", "x.", "x ", "x\x00"):
                for task, query in ((name, "query"), ("task", name)):
                    with self.subTest(task=task, query=query), self.assertRaises(QueryInputError):
                        resolve_query_output_directory(root, task, query)
            output = root / "task" / "query_results" / "query"
            output.mkdir(parents=True)
            with self.assertRaisesRegex(QueryInputError, "already exists"):
                resolve_query_output_directory(root, "task", "query")

    def test_safe_path_name_removes_path_traversal_and_invalid_characters(self):
        self.assertEqual(safe_path_name("../客戶:A?"), "客戶_A")
        self.assertEqual(safe_path_name(""), "untitled")

    def test_query_result_writer_writes_result_lists_to_output_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            writer = QueryResultWriter()
            output_dir = Path(temp_dir).resolve() / "20260524-203000-測試查詢"
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
            downloaded_files_json = json.loads((bundle.path / "downloaded_files.json").read_text(encoding="utf-8"))
            warnings_json = json.loads((bundle.path / "warnings.json").read_text(encoding="utf-8"))

        self.assertEqual(full_text_json[0]["google_file_id"], "file-1")
        self.assertEqual(full_text_json[0]["source_location"], "Drive/Spec.pdf")
        self.assertEqual(
            full_text_json[0]["pages"],
            [{"page_number": 2, "keyword": "spec"}],
        )
        self.assertEqual(vector_json[0]["pages"][0]["page_number"], 1)
        self.assertEqual(query_plan_json["drive_query"], "fullText contains 'spec' and trashed = false")
        self.assertEqual(downloaded_files_json, [])
        self.assertEqual(warnings_json, [])

    def test_reserve_output_directory_creates_parents_and_rejects_existing_directory(self):
        from kbsearch_cli.errors import QueryCliError
        from kbsearch_cli.output import reserve_output_directory

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir).resolve() / "task" / "query_results" / "query-01"

            reserve_output_directory(output_dir)

            self.assertTrue(output_dir.is_dir())
            with self.assertRaisesRegex(QueryCliError, "already exists"):
                reserve_output_directory(output_dir)


if __name__ == "__main__":
    unittest.main()
