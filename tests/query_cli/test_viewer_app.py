import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from pathlib import Path

from kbsearch_cli.viewer_app import (
    find_document_dir,
    find_page_image,
    normalize_downloaded_files,
    inject_image_modal_script,
    inject_tab_tooltips,
)


class ViewerAppTests(unittest.TestCase):
    def test_viewer_scripts_use_supported_iframe_api(self):
        iframe = Mock()
        legacy_html = Mock()
        legacy = SimpleNamespace(html=legacy_html)
        components = SimpleNamespace(v1=legacy)
        with patch.dict("sys.modules", {
            "streamlit": SimpleNamespace(iframe=iframe, components=components),
            "streamlit.components": components,
            "streamlit.components.v1": legacy,
        }):
            inject_image_modal_script()
            inject_tab_tooltips("vector summary", "keyword summary")
        self.assertEqual(iframe.call_count, 2)
        legacy_html.assert_not_called()
        self.assertIn("kbsearch-image-modal", iframe.call_args_list[0].args[0])
        self.assertIn("vector summary", iframe.call_args_list[1].args[0])
        for call in iframe.call_args_list:
            self.assertEqual(call.kwargs, {"height": 1, "tab_index": -1})

    def test_find_page_image_uses_downloaded_files_directory_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            query_dir = Path(temp_dir).resolve() / "query"
            document_dir = query_dir / "same-name-file-1a2b3"
            pages_dir = document_dir / "pages"
            pages_dir.mkdir(parents=True)
            page_image = pages_dir / "0002.png"
            page_image.write_bytes(b"image")

            downloaded_files = normalize_downloaded_files(
                [
                    {
                        "google_file_id": "file-1",
                        "directory": document_dir.as_posix(),
                        "page_paths": [],
                    }
                ]
            )

            result = {"google_file_id": "file-1", "name": "Renamed.pdf"}

            self.assertEqual(find_document_dir(query_dir, result, downloaded_files), document_dir)
            self.assertEqual(find_page_image(query_dir, result, 2, downloaded_files), page_image)

    def test_find_page_image_uses_downloaded_files_page_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            query_dir = Path(temp_dir).resolve() / "query"
            pages_dir = query_dir / "document-file-1a2b3" / "pages"
            pages_dir.mkdir(parents=True)
            page_image = pages_dir / "0003.png"
            page_image.write_bytes(b"image")

            downloaded_files = normalize_downloaded_files(
                [
                    {
                        "google_file_id": "file-1",
                        "directory": pages_dir.parent.as_posix(),
                        "page_paths": [page_image.as_posix()],
                    }
                ]
            )

            result = {"google_file_id": "file-1", "name": "Spec.pdf"}

            self.assertEqual(find_page_image(query_dir, result, 3, downloaded_files), page_image)

    def test_find_page_image_does_not_guess_document_directory_without_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            query_dir = Path(temp_dir).resolve() / "query"
            pages_dir = query_dir / "Spec-file-1a2b3" / "pages"
            pages_dir.mkdir(parents=True)
            (pages_dir / "0002.png").write_bytes(b"image")

            result = {"google_file_id": "file-1", "name": "Spec.pdf"}

            self.assertIsNone(find_document_dir(query_dir, result, {}))
            self.assertIsNone(find_page_image(query_dir, result, 2, {}))


if __name__ == "__main__":
    unittest.main()
