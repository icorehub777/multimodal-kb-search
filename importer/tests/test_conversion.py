import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import app.conversion as conversion
from app.conversion import DocumentConverter, PdfPageRenderer
from app.errors import DocumentConversionError


class ConversionTests(unittest.TestCase):
    def test_pdf_input_returns_source_path_without_conversion(self):
        converter = DocumentConverter()
        source = Path("Spec.pdf")

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self.assertEqual(
                converter.convert_to_pdf(source, "application/pdf", output_dir),
                source,
            )
            self.assertFalse(any(output_dir.iterdir()))

    def test_downloaded_pdf_source_returns_source_path_even_when_original_mime_is_google_native(self):
        converter = DocumentConverter()
        source = Path("GoogleDoc.pdf")

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self.assertEqual(
                converter.convert_to_pdf(
                    source,
                    "application/vnd.google-apps.document",
                    output_dir,
                ),
                source,
            )
            self.assertFalse(any(output_dir.iterdir()))

    def test_google_native_document_mime_returns_exported_source_path(self):
        converter = DocumentConverter()
        source = Path("GoogleDocWithoutPdfSuffix")

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self.assertEqual(
                converter.convert_to_pdf(
                    source,
                    "application/vnd.google-apps.document",
                    output_dir,
                ),
                source,
            )
            self.assertFalse(any(output_dir.iterdir()))

    def test_office_conversion_failure_raises_domain_error(self):
        converter = DocumentConverter()

        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "Spec.docx"
            source.write_text("doc", encoding="utf-8")
            with patch("subprocess.run", side_effect=FileNotFoundError("missing")) as run:
                with self.assertRaises(DocumentConversionError):
                    converter.convert_to_pdf(
                        source,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        Path(temp_dir),
                    )
            self.assertEqual(run.call_args.args[0][0], "soffice")

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
        self.assertEqual([page.path.name for page in pages], ["0001.png", "0002.png"])

    def test_image_page_renderer_normalizes_image_as_single_page_png(self):
        from app.conversion import PageImageRenderer
        from PIL import Image

        renderer = PageImageRenderer()

        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "photo.jpg"
            Image.new("RGB", (1, 1), color=(255, 0, 0)).save(source, format="JPEG")
            pages = renderer.render_pages(source, Path(temp_dir) / "pages")

            self.assertEqual(len(pages), 1)
            self.assertEqual(pages[0].page_number, 1)
            self.assertEqual(pages[0].path.name, "0001.png")
            self.assertTrue(pages[0].path.read_bytes().startswith(b"\x89PNG"))

    def test_text_to_pdf_preserves_chinese_text(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is required for PDF text extraction.")

        cjk_font_path = _available_cjk_font_path()
        if cjk_font_path is None:
            self.skipTest("Configured CJK font is not available.")

        converter = DocumentConverter(cjk_font_path=cjk_font_path)
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "README.md"
            source.write_text(
                "\u4e2d\u6587\u6e2c\u8a66\t\uff1a\u6587\u4ef6\u532f\u5165\n",
                encoding="utf-8",
            )

            output = converter.convert_to_pdf(source, "text/markdown", Path(temp_dir) / "pdf")

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

        cjk_font_path = _available_cjk_font_path()
        if cjk_font_path is None:
            self.skipTest("Configured CJK font is not available.")

        converter = DocumentConverter(cjk_font_path=cjk_font_path)
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "README.md"
            source.write_text("\u4e2d" * 120, encoding="utf-8")

            output = converter.convert_to_pdf(source, "text/markdown", Path(temp_dir) / "pdf")

            with fitz.open(output) as document:
                text = document[0].get_text("text")

        self.assertGreaterEqual(len([line for line in text.splitlines() if line]), 3)

    def test_cjk_font_name_uses_only_configured_font_path(self):
        registered_fonts = set()

        class FakePdfMetrics:
            @staticmethod
            def getRegisteredFontNames():
                return registered_fonts

            @staticmethod
            def registerFont(_font):
                registered_fonts.add(conversion.CJK_TEXT_FONT_NAME)

        with TemporaryDirectory() as temp_dir:
            configured_font = Path(temp_dir) / "configured.ttf"
            configured_font.write_bytes(b"font")
            seen_paths = []

            def fake_tt_font(_font_name, font_path):
                seen_paths.append(font_path)
                return object()

            with patch(
                "reportlab.pdfbase.pdfmetrics.getRegisteredFontNames",
                side_effect=FakePdfMetrics.getRegisteredFontNames,
            ), patch(
                "reportlab.pdfbase.pdfmetrics.registerFont",
                side_effect=FakePdfMetrics.registerFont,
            ), patch("reportlab.pdfbase.ttfonts.TTFont", side_effect=fake_tt_font):
                self.assertEqual(
                    conversion._text_pdf_font_name("\u4e2d", configured_font),
                    conversion.CJK_TEXT_FONT_NAME,
                )

        self.assertEqual(seen_paths, [str(configured_font)])

    def test_cjk_font_name_rejects_missing_configured_font_path(self):
        with self.assertRaises(DocumentConversionError):
            conversion._text_pdf_font_name("\u4e2d", Path("C:/missing/font.ttf"))


def _available_cjk_font_path() -> Path | None:
    for font_path in (
        Path("C:/Windows/Fonts/msjh.ttc"),
        Path("C:/Windows/Fonts/NotoSansTC-VF.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    ):
        if font_path.exists():
            return font_path
    return None


if __name__ == "__main__":
    unittest.main()
