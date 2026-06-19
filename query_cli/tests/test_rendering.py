import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
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
