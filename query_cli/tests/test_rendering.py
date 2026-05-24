import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import kbsearch_cli.rendering as rendering
from kbsearch_cli.errors import DocumentRenderError
from kbsearch_cli.rendering import DocumentPageRenderer


class RenderingTests(unittest.TestCase):
    def test_text_to_pdf_preserves_chinese_text(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is required for PDF text extraction.")

        renderer = DocumentPageRenderer()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "README.md"
            source.write_text("中文測試\t：文件查詢\n", encoding="utf-8")

            try:
                output = renderer._convert_text_to_pdf(source, Path(temp_dir))
            except DocumentRenderError as exc:
                if "CJK font" in str(exc):
                    self.skipTest("No CJK font installed.")
                raise

            with fitz.open(output) as document:
                text = document[0].get_text("text")

        self.assertIn("中文測試", text)
        self.assertIn("文件查詢", text)

    def test_cjk_font_path_env_takes_precedence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            configured_font = Path(temp_dir) / "custom-cjk.ttf"
            configured_font.write_bytes(b"font")

            with patch.dict(os.environ, {"KBSEARCH_CJK_FONT_PATH": str(configured_font)}):
                with patch.object(rendering, "CJK_TEXT_FONT_CANDIDATES", (Path("fallback.ttf"),)):
                    self.assertEqual(
                        rendering._cjk_text_font_candidates(),
                        (configured_font, Path("fallback.ttf")),
                    )


if __name__ == "__main__":
    unittest.main()
