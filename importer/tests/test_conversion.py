import sys
import unittest
from io import StringIO
import logging
from pathlib import Path
from subprocess import CompletedProcess
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

    def test_office_conversion_uses_short_temp_path_when_source_path_is_too_long(self):
        converter = DocumentConverter()

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            long_name = (
                "internal_"
                + ("Bell Taih US CA Unshipped Order Status - 20260522" * 3)
                + ".pptx"
            )
            source_dir = root / "work" / long_name.replace(".pptx", "-file-id")
            source_dir.mkdir(parents=True)
            source_path = source_dir / long_name
            source_path.write_bytes(b"pptx")

            def fake_run(command, **_kwargs):
                convert_source = Path(command[-1])
                convert_outdir = Path(command[-2])
                self.assertEqual(convert_source.name, "source.pptx")
                self.assertLessEqual(
                    len(str(convert_source.resolve())),
                    conversion._LIBREOFFICE_MAX_SOURCE_PATH,
                )
                (convert_outdir / "source.pdf").write_bytes(b"pdf")
                return CompletedProcess(command, 0, "", "")

            with patch("app.conversion.subprocess.run", side_effect=fake_run):
                output_path = converter.convert_to_pdf(
                    source_path,
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    source_dir,
                )

            self.assertEqual(output_path, source_dir / f"{source_path.stem}.pdf")
            self.assertTrue(output_path.exists())

    def test_pdf_page_renderer_returns_numbered_page_images(self):
        class FakePage:
            rect = type("Rect", (), {"width": 612, "height": 792})()

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
            class FakeTools:
                @staticmethod
                def mupdf_display_errors(value):
                    return not value

            class FakeFitz:
                TOOLS = FakeTools()

                @staticmethod
                def open(_pdf_path):
                    return FakeDocument()

            with patch.dict(sys.modules, {"fitz": FakeFitz}):
                pages = renderer.render_pages(Path("Spec.pdf"), Path(temp_dir))

        self.assertEqual([page.page_number for page in pages], [1, 2])
        self.assertEqual([page.path.name for page in pages], ["0001.png", "0002.png"])

    def test_pdf_page_renderer_reduces_dpi_to_stay_within_max_pixels(self):
        seen_dpi = []

        class FakePage:
            rect = type("Rect", (), {"width": 11_480, "height": 5_149})()

            def get_pixmap(self, dpi):
                seen_dpi.append(dpi)

                class Pixmap:
                    def save(self, path):
                        Path(path).write_bytes(b"png")

                return Pixmap()

        class FakeDocument:
            def __enter__(self):
                return [FakePage()]

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeTools:
            @staticmethod
            def mupdf_display_errors(value):
                return not value

        class FakeFitz:
            TOOLS = FakeTools()

            @staticmethod
            def open(_pdf_path):
                return FakeDocument()

        renderer = PdfPageRenderer(target_dpi=200, max_pixels=80_000_000)
        with TemporaryDirectory() as temp_dir:
            with patch.dict(sys.modules, {"fitz": FakeFitz}):
                renderer.render_pages(Path("oversized.pdf"), Path(temp_dir))

        self.assertEqual(seen_dpi, [83])

    def test_pdf_page_renderer_suppresses_and_restores_mupdf_errors(self):
        display_error_values = []

        class FakeTools:
            @staticmethod
            def mupdf_display_errors(value):
                display_error_values.append(value)
                return True

        class FakeDocument:
            def __enter__(self):
                return []

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeFitz:
            TOOLS = FakeTools()

            @staticmethod
            def open(_pdf_path):
                return FakeDocument()

        renderer = PdfPageRenderer()
        with TemporaryDirectory() as temp_dir:
            with patch.dict(sys.modules, {"fitz": FakeFitz}):
                renderer.render_pages(Path("Spec.pdf"), Path(temp_dir))

        self.assertEqual(display_error_values, [False, True])

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

    def test_image_page_renderer_applies_exif_orientation(self):
        from app.conversion import PageImageRenderer
        from PIL import Image

        renderer = PageImageRenderer()

        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "rotated.jpg"
            image = Image.new("RGB", (2, 3), color=(255, 0, 0))
            exif = image.getexif()
            exif[274] = 6
            image.save(source, format="JPEG", exif=exif)

            pages = renderer.render_pages(source, Path(temp_dir) / "pages")

            with Image.open(pages[0].path) as rendered:
                self.assertEqual(rendered.size, (3, 2))

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

    def test_text_to_pdf_supports_cp950_and_logs_selected_encoding(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is required for PDF text extraction.")

        cjk_font_path = _available_cjk_font_path()
        if cjk_font_path is None:
            self.skipTest("Configured CJK font is not available.")

        stream = StringIO()
        logger = logging.getLogger("app.tests.conversion.encoding")
        logger.handlers = [logging.StreamHandler(stream)]
        logger.setLevel(logging.INFO)
        logger.propagate = False
        converter = DocumentConverter(cjk_font_path=cjk_font_path, logger=logger)
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "legacy.txt"
            source.write_bytes("繁體中文測試".encode("cp950"))

            output = converter.convert_to_pdf(source, "text/plain", Path(temp_dir) / "pdf")

            with fitz.open(output) as document:
                text = document[0].get_text("text")

        self.assertIn("繁體中文測試", text)
        self.assertIn("encoding=cp950", stream.getvalue())

    def test_text_to_pdf_honors_utf16_bom(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is required for PDF text extraction.")

        cjk_font_path = _available_cjk_font_path()
        if cjk_font_path is None:
            self.skipTest("Configured CJK font is not available.")

        converter = DocumentConverter(cjk_font_path=cjk_font_path)
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "utf16.txt"
            source.write_bytes("UTF-16 中文".encode("utf-16"))

            output = converter.convert_to_pdf(source, "text/plain", Path(temp_dir) / "pdf")

            with fitz.open(output) as document:
                text = document[0].get_text("text")

        self.assertIn("UTF-16 中文", text)

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
