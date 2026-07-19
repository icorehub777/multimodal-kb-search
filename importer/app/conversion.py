from __future__ import annotations

import codecs
import logging
import math
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from app.document_importer import PageImage
from app.document_processing import classify_document_type, page_png_path
from app.errors import DocumentConversionError
from app.logging_config import LOGGER_NAME

CJK_TEXT_FONT_NAME = "KBSearchTextCJK"
_LIBREOFFICE_MAX_SOURCE_PATH = 240
SOFFICE_EXECUTABLE = "soffice"


class DocumentConverter:
    def __init__(
        self,
        cjk_font_path: Path | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._cjk_font_path = cjk_font_path
        self._logger = logger or logging.getLogger(LOGGER_NAME)

    def convert_to_pdf(self, source_path: Path, mime_type: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)

        if source_path.suffix.lower() == ".pdf":
            return source_path

        document_type = classify_document_type(mime_type)
        if document_type == "pdf":
            return source_path
        if document_type == "image":
            return source_path
        if document_type in {"word", "powerpoint"}:
            return self._convert_office_to_pdf(source_path, output_dir)
        if document_type in {"txt", "md"}:
            return self._convert_text_to_pdf(source_path, output_dir)

        raise DocumentConversionError(f"Unsupported document type: {document_type}")

    def _convert_office_to_pdf(self, source_path: Path, output_dir: Path) -> Path:
        output_path = output_dir / f"{source_path.stem}.pdf"
        try:
            with _office_conversion_inputs(source_path) as (convert_source, convert_outdir):
                result = subprocess.run(
                    [
                        SOFFICE_EXECUTABLE,
                        "--headless",
                        "--convert-to",
                        "pdf",
                        "--outdir",
                        str(convert_outdir),
                        str(convert_source),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    for partial_pdf in {convert_outdir / f"{convert_source.stem}.pdf", output_path}:
                        if partial_pdf.exists():
                            partial_pdf.unlink()
                    raise DocumentConversionError(
                        f"Office to PDF conversion failed for {source_path}: "
                        f"{result.stderr.strip()}"
                    )
                produced_pdf = convert_outdir / f"{convert_source.stem}.pdf"
                if produced_pdf != output_path:
                    if not produced_pdf.exists():
                        raise DocumentConversionError(
                            f"Office conversion did not create PDF: {produced_pdf}"
                        )
                    shutil.move(str(produced_pdf), str(output_path))
        except OSError as exc:
            raise DocumentConversionError(f"Office to PDF conversion failed: {source_path}") from exc

        if not output_path.exists():
            raise DocumentConversionError(f"Office conversion did not create PDF: {output_path}")
        return output_path

    def _convert_text_to_pdf(self, source_path: Path, output_dir: Path) -> Path:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfgen import canvas
        except ImportError as exc:
            raise DocumentConversionError("reportlab is required for TXT/MD conversion.") from exc

        output_path = output_dir / f"{source_path.stem}.pdf"
        text, encoding = _read_text(source_path)
        self._logger.info("text_decode path=%s encoding=%s", source_path, encoding)
        text = text.expandtabs(4)
        font_name = _text_pdf_font_name(text, self._cjk_font_path)
        pdf = canvas.Canvas(str(output_path), pagesize=A4)
        width, height = A4
        x = 20 * mm
        y = height - 20 * mm
        line_height = 14
        font_size = 11
        max_line_width = width - (40 * mm)
        pdf.setFont(font_name, font_size)

        for line in text.splitlines() or [""]:
            chunks = _wrap_text_line(
                line,
                font_name=font_name,
                font_size=font_size,
                max_width=max_line_width,
                string_width=pdfmetrics.stringWidth,
            )
            for chunk in chunks:
                if y < 20 * mm:
                    pdf.showPage()
                    y = height - 20 * mm
                    pdf.setFont(font_name, font_size)
                pdf.drawString(x, y, chunk)
                y -= line_height
        pdf.save()
        return output_path


def _read_text(source_path: Path) -> tuple[str, str]:
    data = source_path.read_bytes()
    bom_encodings = (
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF32_LE, "utf-32"),
        (codecs.BOM_UTF32_BE, "utf-32"),
        (codecs.BOM_UTF16_LE, "utf-16"),
        (codecs.BOM_UTF16_BE, "utf-16"),
    )
    for bom, encoding in bom_encodings:
        if data.startswith(bom):
            try:
                return data.decode(encoding), encoding
            except UnicodeDecodeError as exc:
                raise DocumentConversionError(
                    f"Text decoding failed for {source_path} with BOM encoding {encoding}."
                ) from exc

    for encoding in ("utf-8", "cp950"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue

    raise DocumentConversionError(
        f"Text decoding failed for {source_path}. "
        "Supported encodings: UTF-8, UTF-16/32 with BOM, CP950."
    )


class PdfPageRenderer:
    def __init__(
        self,
        target_dpi: int = 200,
        max_pixels: int = 80_000_000,
        logger: logging.Logger | None = None,
    ) -> None:
        self._target_dpi = target_dpi
        self._max_pixels = max_pixels
        self._logger = logger or logging.getLogger(LOGGER_NAME)

    def render_pages(self, pdf_path: Path, output_dir: Path) -> list[PageImage]:
        if pdf_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            return PageImageRenderer().render_pages(pdf_path, output_dir)

        try:
            import fitz
        except ImportError as exc:
            raise DocumentConversionError("PyMuPDF is required for PDF page rendering.") from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        pages: list[PageImage] = []
        previous_display_errors = fitz.TOOLS.mupdf_display_errors(False)
        try:
            with fitz.open(pdf_path) as document:
                for index, page in enumerate(document, start=1):
                    output_path = page_png_path(output_dir, index)
                    render_dpi = _page_render_dpi(
                        page.rect.width,
                        page.rect.height,
                        self._target_dpi,
                        self._max_pixels,
                    )
                    self._logger.info(
                        "pdf_render page=%s target_dpi=%s render_dpi=%s "
                        "page_width_points=%s page_height_points=%s max_pixels=%s",
                        index,
                        self._target_dpi,
                        render_dpi,
                        page.rect.width,
                        page.rect.height,
                        self._max_pixels,
                    )
                    page.get_pixmap(dpi=render_dpi).save(output_path)
                    pages.append(PageImage(page_number=index, path=output_path))
        finally:
            fitz.TOOLS.mupdf_display_errors(previous_display_errors)
        return pages


def _page_render_dpi(
    width_points: float,
    height_points: float,
    target_dpi: int,
    max_pixels: int,
) -> int:
    target_pixels = (
        width_points * target_dpi / 72
    ) * (
        height_points * target_dpi / 72
    )
    if target_pixels <= max_pixels:
        return target_dpi
    scale = math.sqrt(max_pixels / target_pixels)
    return max(1, math.floor(target_dpi * scale))


class PageImageRenderer:
    def render_pages(self, image_path: Path, output_dir: Path) -> list[PageImage]:
        try:
            from PIL import Image, ImageOps
        except ImportError as exc:
            raise DocumentConversionError("Pillow is required for image page rendering.") from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = page_png_path(output_dir, 1)
        with Image.open(image_path) as image:
            ImageOps.exif_transpose(image).convert("RGB").save(output_path, format="PNG")
        return [PageImage(page_number=1, path=output_path)]


def _text_pdf_font_name(text: str, cjk_font_path: Path | None) -> str:
    if not _has_cjk_text(text):
        return "Helvetica"

    if cjk_font_path is None:
        raise DocumentConversionError("CJK TXT/MD conversion requires KBSEARCH_CJK_FONT_PATH.")

    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError as exc:
        raise DocumentConversionError("reportlab is required for CJK TXT/MD conversion.") from exc

    if CJK_TEXT_FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return CJK_TEXT_FONT_NAME

    if cjk_font_path.exists():
        try:
            pdfmetrics.registerFont(TTFont(CJK_TEXT_FONT_NAME, str(cjk_font_path)))
            return CJK_TEXT_FONT_NAME
        except Exception as exc:
            raise DocumentConversionError(f"Unable to register CJK font: {cjk_font_path}") from exc

    raise DocumentConversionError(f"CJK font file not found: {cjk_font_path}")


def _has_cjk_text(text: str) -> bool:
    return any(
        "\u3400" <= character <= "\u9fff" or "\uf900" <= character <= "\ufaff"
        for character in text
    )


@contextmanager
def _office_conversion_inputs(source_path: Path):
    if len(str(source_path.resolve())) <= _LIBREOFFICE_MAX_SOURCE_PATH:
        yield source_path, source_path.parent
        return

    with tempfile.TemporaryDirectory(prefix="kbsearch-lo-") as temp_dir:
        temp_root = Path(temp_dir)
        temp_source = temp_root / f"source{source_path.suffix.lower()}"
        shutil.copy2(source_path, temp_source)
        yield temp_source, temp_root


def _wrap_text_line(
    line: str,
    *,
    font_name: str,
    font_size: int,
    max_width: float,
    string_width,
) -> list[str]:
    if line == "":
        return [""]

    chunks: list[str] = []
    current = ""
    for character in line:
        candidate = current + character
        if current and string_width(candidate, font_name, font_size) > max_width:
            chunks.append(current)
            current = character
        else:
            current = candidate

    if current:
        chunks.append(current)
    return chunks
