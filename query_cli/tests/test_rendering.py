import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import kbsearch_cli.rendering as rendering
from kbsearch_cli.errors import DocumentRenderError
from kbsearch_cli.rendering import DocumentPageRenderer, parse_page_numbers


class RenderingTests(unittest.TestCase):
    def test_parse_page_numbers_supports_lists_ranges_and_deduplication(self):
        self.assertEqual(parse_page_numbers("3,5,8-10,5"), [3, 5, 8, 9, 10])

    def test_parse_page_numbers_rejects_invalid_values(self):
        for value in ("", "0", "-1", "3-1", "1,,2", "abc"):
            with self.subTest(value=value):
                with self.assertRaises(DocumentRenderError):
                    parse_page_numbers(value)

    def test_text_to_pdf_preserves_chinese_text(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is required for PDF text extraction.")

        cjk_font_path = _available_cjk_font_path()
        if cjk_font_path is None:
            self.skipTest("Configured CJK font is not available.")

        renderer = DocumentPageRenderer(cjk_font_path=cjk_font_path)
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "README.md"
            source.write_text("中文測試\t：文件查詢\n", encoding="utf-8")

            output = renderer._convert_text_to_pdf(source, Path(temp_dir))

            with fitz.open(output) as document:
                text = document[0].get_text("text")

        self.assertIn("中文測試", text)
        self.assertIn("文件查詢", text)

    def test_cjk_font_name_uses_only_configured_font_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            configured_font = Path(temp_dir) / "custom-cjk.ttf"
            configured_font.write_bytes(b"font")
            seen_paths = []

            class FakePdfMetrics:
                @staticmethod
                def getRegisteredFontNames():
                    return set()

                @staticmethod
                def registerFont(_font):
                    return None

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
                    rendering._text_pdf_font_name("\u4e2d", configured_font),
                    rendering.CJK_TEXT_FONT_NAME,
                )

        self.assertEqual(seen_paths, [str(configured_font)])

    def test_convert_office_to_pdf_uses_short_temp_path_when_source_path_is_too_long(self):
        renderer = DocumentPageRenderer()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            long_name = "內部_" + ("Bell Taih US CA Unshipped Order Status - 20260522" * 3) + ".pptx"
            source_dir = root / "bundle" / long_name.replace(".pptx", "-file-id")
            source_dir.mkdir(parents=True)
            source_path = source_dir / long_name
            source_path.write_bytes(b"pptx")

            def fake_run(command, **_kwargs):
                self.assertEqual(command[0], "soffice")
                convert_source = Path(command[-1])
                convert_outdir = Path(command[-2])
                self.assertEqual(convert_source.name, "source.pptx")
                self.assertTrue(str(convert_source).startswith(str(Path(tempfile.gettempdir()))))
                (convert_outdir / "source.pdf").write_bytes(b"pdf")
                return CompletedProcess(command, 0, "", "")

            with patch("kbsearch_cli.rendering.subprocess.run", side_effect=fake_run):
                output_path = renderer._convert_office_to_pdf(source_path, source_dir)

            self.assertEqual(output_path, source_dir / f"{source_path.stem}.pdf")
            self.assertTrue(output_path.exists())

    def test_convert_office_to_pdf_does_not_leave_pdf_when_libreoffice_fails(self):
        renderer = DocumentPageRenderer()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            long_name = "內部_" + ("Bell Taih US CA Unshipped Order Status - 20260522" * 3) + ".pptx"
            source_dir = root / "bundle" / long_name.replace(".pptx", "-file-id")
            source_dir.mkdir(parents=True)
            source_path = source_dir / long_name
            source_path.write_bytes(b"pptx")
            expected_output = source_dir / f"{source_path.stem}.pdf"

            def fake_run(command, **_kwargs):
                convert_outdir = Path(command[-2])
                (convert_outdir / "source.pdf").write_bytes(b"partial-pdf")
                return CompletedProcess(command, 1, "", "conversion failed")

            with patch("kbsearch_cli.rendering.subprocess.run", side_effect=fake_run):
                with self.assertRaises(DocumentRenderError):
                    renderer._convert_office_to_pdf(source_path, source_dir)

            self.assertFalse(expected_output.exists())

    def test_extract_pdf_text_writes_one_utf8_file_per_page(self):
        renderer = DocumentPageRenderer()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pdf_path = root / "sample.pdf"
            _create_pdf(pdf_path, ["first page", "second page"])

            paths = renderer.extract_pdf_text(pdf_path, root / "text")

            self.assertEqual([path.name for path in paths], ["0001.txt", "0002.txt"])
            self.assertIn("first page", paths[0].read_text(encoding="utf-8"))
            self.assertIn("second page", paths[1].read_text(encoding="utf-8"))

    def test_process_copies_pdf_to_standard_document_path(self):
        renderer = DocumentPageRenderer(dpi=72)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "original-name.pdf"
            _create_pdf(source_path, ["first page"])
            output_dir = root / "result"
            output_dir.mkdir()
            copied_source = output_dir / source_path.name
            copied_source.write_bytes(source_path.read_bytes())

            processed = renderer.process(
                copied_source,
                "application/pdf",
                output_dir,
                [1],
            )

            self.assertEqual(processed.pdf_path, output_dir / "pdf" / "document.pdf")
            self.assertTrue(copied_source.exists())
            self.assertTrue(processed.pdf_path.exists())
            self.assertEqual([path.name for path in processed.text_paths], ["0001.txt"])
            self.assertEqual([path.name for path in processed.page_paths], ["0001.png"])

    def test_process_keeps_spreadsheet_without_derived_files(self):
        renderer = DocumentPageRenderer()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "orders.xlsx"
            source_path.write_bytes(b"xlsx")

            processed = renderer.process(
                source_path,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                root,
                [],
            )

            self.assertIsNone(processed.pdf_path)
            self.assertEqual(processed.text_paths, [])
            self.assertEqual(processed.page_paths, [])
            self.assertFalse((root / "pdf").exists())

    def test_process_only_normalizes_vector_hit_image(self):
        from PIL import Image

        renderer = DocumentPageRenderer()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "photo.jpg"
            Image.new("RGB", (2, 2), color=(255, 0, 0)).save(source_path)

            full_text_only = renderer.process(source_path, "image/jpeg", root, [])
            vector_hit = renderer.process(source_path, "image/jpeg", root, [1])

            self.assertEqual(full_text_only.page_paths, [])
            self.assertEqual([path.name for path in vector_hit.page_paths], ["0001.png"])
            self.assertFalse((root / "pdf").exists())

    def test_process_uses_mime_type_for_pdf_without_extension(self):
        renderer = DocumentPageRenderer(dpi=72)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "downloaded"
            _create_pdf(source_path, ["first page"])
            output_dir = root / "result"

            processed = renderer.process(source_path, "application/pdf", output_dir, [1])

            self.assertEqual(processed.pdf_path, output_dir / "pdf" / "document.pdf")
            self.assertEqual([path.name for path in processed.text_paths], ["0001.txt"])
            self.assertEqual([path.name for path in processed.page_paths], ["0001.png"])

    def test_process_uses_mime_type_for_image_without_extension(self):
        from PIL import Image

        renderer = DocumentPageRenderer()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "downloaded"
            Image.new("RGB", (2, 2), color=(255, 0, 0)).save(source_path, format="JPEG")

            processed = renderer.process(source_path, "image/jpeg", root, [1])

            self.assertEqual(processed.pdf_path, None)
            self.assertEqual(processed.text_paths, [])
            self.assertEqual([path.name for path in processed.page_paths], ["0001.png"])

    def test_render_pdf_pages_only_renders_requested_pages(self):
        renderer = DocumentPageRenderer(dpi=72)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pdf_path = root / "sample.pdf"
            _create_pdf(pdf_path, ["one", "two", "three"])
            pages_dir = root / "pages"
            pages_dir.mkdir()
            existing_path = pages_dir / "0001.png"
            existing_path.write_bytes(b"existing")

            paths = renderer.render_pdf_pages(pdf_path, pages_dir, [3, 1, 3])

            self.assertEqual([path.name for path in paths], ["0001.png", "0003.png"])
            self.assertTrue(existing_path.read_bytes().startswith(b"\x89PNG"))
            self.assertFalse((pages_dir / "0002.png").exists())

    def test_render_pdf_pages_rejects_page_beyond_document(self):
        renderer = DocumentPageRenderer()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pdf_path = root / "sample.pdf"
            _create_pdf(pdf_path, ["one"])

            with self.assertRaisesRegex(DocumentRenderError, "outside PDF page range"):
                renderer.render_pdf_pages(pdf_path, root / "pages", [2])


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


def _create_pdf(path: Path, page_texts: list[str]) -> None:
    import fitz

    with fitz.open() as document:
        for text in page_texts:
            page = document.new_page()
            page.insert_text((72, 72), text)
        document.save(path)


if __name__ == "__main__":
    unittest.main()
