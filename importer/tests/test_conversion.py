import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import kbsearch_importer.conversion as conversion
from kbsearch_importer.conversion import DocumentConverter, PdfPageRenderer
from kbsearch_importer.errors import DocumentConversionError


class ConversionTests(unittest.TestCase):
    def test_pdf_input_returns_source_path_without_conversion(self):
        converter = DocumentConverter()
        source = Path("Spec.pdf")

        self.assertEqual(converter.convert_to_pdf(source, "application/pdf", Path("out")), source)

    def test_downloaded_pdf_source_returns_source_path_even_when_original_mime_is_google_native(self):
        converter = DocumentConverter()
        source = Path("GoogleDoc.pdf")

        self.assertEqual(
            converter.convert_to_pdf(source, "application/vnd.google-apps.document", Path("out")),
            source,
        )

    def test_google_native_document_mime_returns_exported_source_path(self):
        converter = DocumentConverter()
        source = Path("GoogleDocWithoutPdfSuffix")

        self.assertEqual(
            converter.convert_to_pdf(source, "application/vnd.google-apps.document", Path("out")),
            source,
        )

    def test_office_conversion_failure_raises_domain_error(self):
        converter = DocumentConverter(libreoffice_command="missing-libreoffice")

        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "Spec.docx"
            source.write_text("doc", encoding="utf-8")
            with patch("subprocess.run", side_effect=FileNotFoundError("missing")):
                with self.assertRaises(DocumentConversionError):
                    converter.convert_to_pdf(
                        source,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        Path(temp_dir),
                    )

    def test_pdf_page_renderer_returns_numbered_page_images(self):
        class FakePage:
            def get_pixmap(self, dpi):
                class Pixmap:
                    def save(self, path):
                        Path(path).write_bytes(b"png")

                return Pixmap()

        class FakeDocument:
            def __enter__(self):
                return [FakePage(), FakePage()]

            def __exit__(self, exc_type, exc, tb):
                return False

        renderer = PdfPageRenderer()

        with TemporaryDirectory() as temp_dir:
            class FakeFitz:
                @staticmethod
                def open(_pdf_path):
                    return FakeDocument()

            with patch.dict(sys.modules, {"fitz": FakeFitz}):
                pages = renderer.render_pages(Path("Spec.pdf"), Path(temp_dir))

        self.assertEqual([page.page_number for page in pages], [1, 2])
        self.assertEqual([page.path.name for page in pages], ["01.png", "02.png"])

    def test_image_page_renderer_normalizes_image_as_single_page_png(self):
        from kbsearch_importer.conversion import PageImageRenderer
        from PIL import Image

        renderer = PageImageRenderer()

        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "photo.jpg"
            Image.new("RGB", (1, 1), color=(255, 0, 0)).save(source, format="JPEG")
            pages = renderer.render_pages(source, Path(temp_dir) / "pages")

            self.assertEqual(len(pages), 1)
            self.assertEqual(pages[0].page_number, 1)
            self.assertEqual(pages[0].path.name, "01.png")
            self.assertTrue(pages[0].path.read_bytes().startswith(b"\x89PNG"))

    def test_text_to_pdf_preserves_chinese_text(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is required for PDF text extraction.")

        converter = DocumentConverter()
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "README.md"
            source.write_text(
                "\u4e2d\u6587\u6e2c\u8a66\t\uff1a\u6587\u4ef6\u532f\u5165\n",
                encoding="utf-8",
            )

            try:
                output = converter.convert_to_pdf(source, "text/markdown", Path(temp_dir) / "pdf")
            except DocumentConversionError as exc:
                if "CJK font" in str(exc):
                    self.skipTest("No CJK font installed.")
                raise

            with fitz.open(output) as document:
                text = document[0].get_text("text")

        self.assertIn("\u4e2d\u6587\u6e2c\u8a66", text)
        self.assertIn("\u6587\u4ef6\u532f\u5165", text)
        self.assertNotIn("\x00", text)

    def test_text_to_pdf_wraps_long_chinese_lines(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is required for PDF text extraction.")

        converter = DocumentConverter()
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "README.md"
            source.write_text("\u4e2d" * 120, encoding="utf-8")

            try:
                output = converter.convert_to_pdf(source, "text/markdown", Path(temp_dir) / "pdf")
            except DocumentConversionError as exc:
                if "CJK font" in str(exc):
                    self.skipTest("No CJK font installed.")
                raise

            with fitz.open(output) as document:
                text = document[0].get_text("text")

        self.assertGreaterEqual(len([line for line in text.splitlines() if line]), 3)

    def test_cjk_font_path_env_takes_precedence(self):
        with TemporaryDirectory() as temp_dir:
            configured_font = Path(temp_dir) / "custom-cjk.ttf"
            configured_font.write_bytes(b"font")

            with patch.dict(os.environ, {"KBSEARCH_CJK_FONT_PATH": str(configured_font)}):
                with patch.object(conversion, "CJK_TEXT_FONT_CANDIDATES", (Path("fallback.ttf"),)):
                    self.assertEqual(
                        conversion._cjk_text_font_candidates(),
                        (configured_font, Path("fallback.ttf")),
                    )

    def test_invalid_cjk_font_candidate_tries_next_candidate(self):
        registered_fonts = set()

        class FakePdfMetrics:
            @staticmethod
            def getRegisteredFontNames():
                return registered_fonts

            @staticmethod
            def registerFont(_font):
                registered_fonts.add(conversion.CJK_TEXT_FONT_NAME)

        def fake_tt_font(_font_name, font_path):
            if font_path.endswith("bad.ttf"):
                raise RuntimeError("bad font")
            return object()

        with TemporaryDirectory() as temp_dir:
            bad_font = Path(temp_dir) / "bad.ttf"
            good_font = Path(temp_dir) / "good.ttf"
            bad_font.write_bytes(b"bad")
            good_font.write_bytes(b"good")

            with patch.object(conversion, "_cjk_text_font_candidates", return_value=(bad_font, good_font)):
                with patch.dict(
                    sys.modules,
                    {
                        "reportlab.pdfbase.pdfmetrics": FakePdfMetrics,
                        "reportlab.pdfbase.ttfonts": type("FakeTtFonts", (), {"TTFont": fake_tt_font}),
                    },
                ):
                    self.assertEqual(
                        conversion._text_pdf_font_name("\u4e2d"),
                        conversion.CJK_TEXT_FONT_NAME,
                    )


if __name__ == "__main__":
    unittest.main()
