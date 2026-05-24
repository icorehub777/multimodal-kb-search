import unittest
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
