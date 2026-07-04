from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from kbsearch_cli.errors import DocumentRenderError
from kbsearch_cli.models import ProcessedDocument

CJK_TEXT_FONT_NAME = "KBSearchTextCJK"
_LIBREOFFICE_MAX_SOURCE_PATH = 240
SOFFICE_EXECUTABLE = "soffice"
# Keep this map aligned with importer/app/document_processing.py.
_MIME_TYPE_TO_DOCUMENT_TYPE = {
    "application/pdf": "pdf",
    "application/vnd.google-apps.document": "pdf",
    "application/vnd.google-apps.presentation": "pdf",
    "application/msword": "word",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "word",
    "application/vnd.ms-powerpoint": "powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "powerpoint",
    "text/plain": "txt",
    "text/markdown": "md",
    "image/png": "image",
    "image/jpeg": "image",
    "image/webp": "image",
}
# Keep this set aligned with importer/app/document_processing.py.
_SPREADSHEET_MIME_TYPES = {
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.google-apps.spreadsheet",
}


def classify_document_type(mime_type: str) -> str:
    if mime_type in _SPREADSHEET_MIME_TYPES:
        return "spreadsheet"

    document_type = _MIME_TYPE_TO_DOCUMENT_TYPE.get(mime_type)
    if document_type is None:
        return "download_only"
    return document_type


class DocumentPageRenderer:
    def __init__(
        self,
        cjk_font_path: Path | None = None,
        dpi: int = 200,
    ) -> None:
        self._cjk_font_path = cjk_font_path
        self._dpi = dpi

    def process(
        self,
        source_path: Path,
        mime_type: str,
        output_dir: Path,
        page_numbers: list[int],
    ) -> ProcessedDocument:
        document_type = classify_document_type(mime_type)
        if document_type in {"spreadsheet", "download_only"}:
            return ProcessedDocument(pdf_path=None, text_paths=[], page_paths=[])
        if document_type == "image":
            if not page_numbers:
                return ProcessedDocument(pdf_path=None, text_paths=[], page_paths=[])
            if set(page_numbers) != {1}:
                raise DocumentRenderError("Image documents only support page 1.")
            return ProcessedDocument(
                pdf_path=None,
                text_paths=[],
                page_paths=self._render_image(source_path, output_dir / "pages"),
            )

        pdf_path = self.prepare_pdf(source_path, mime_type, output_dir)
        text_paths = self.extract_pdf_text(pdf_path, output_dir / "text")
        page_paths = self.render_pdf_pages(pdf_path, output_dir / "pages", page_numbers)
        return ProcessedDocument(
            pdf_path=pdf_path,
            text_paths=text_paths,
            page_paths=page_paths,
        )

    def prepare_pdf(self, source_path: Path, mime_type: str, output_dir: Path) -> Path:
        pdf_dir = output_dir / "pdf"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        output_path = pdf_dir / "document.pdf"
        if classify_document_type(mime_type) == "pdf":
            shutil.copy2(source_path, output_path)
            return output_path

        converted_path = self._render_source_path(source_path, mime_type, output_dir)
        if converted_path.resolve() != output_path.resolve():
            shutil.move(str(converted_path), str(output_path))
        return output_path

    def _render_source_path(self, source_path: Path, mime_type: str, output_dir: Path) -> Path:
        document_type = classify_document_type(mime_type)
        if document_type in {"word", "powerpoint"}:
            return self._convert_office_to_pdf(source_path, output_dir)
        if document_type in {"txt", "md"}:
            return self._convert_text_to_pdf(source_path, output_dir)
        raise DocumentRenderError(f"Unsupported document MIME type: {mime_type}")

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
                    raise DocumentRenderError(
                        f"Office to PDF conversion failed for {source_path}: {result.stderr.strip()}"
                    )
                produced_pdf = convert_outdir / f"{convert_source.stem}.pdf"
                if produced_pdf != output_path:
                    if not produced_pdf.exists():
                        raise DocumentRenderError(
                            f"Office conversion did not create PDF: {produced_pdf}"
                        )
                    shutil.move(str(produced_pdf), str(output_path))
        except OSError as exc:
            raise DocumentRenderError(f"Office to PDF conversion failed: {source_path}") from exc
        if not output_path.exists():
            raise DocumentRenderError(f"Office conversion did not create PDF: {output_path}")
        return output_path

    def _convert_text_to_pdf(self, source_path: Path, output_dir: Path) -> Path:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfgen import canvas
        except ImportError as exc:
            raise DocumentRenderError("reportlab is required for TXT/MD conversion.") from exc

        output_path = output_dir / f"{source_path.stem}.pdf"
        text = source_path.read_text(encoding="utf-8").expandtabs(4)
        font_name = _text_pdf_font_name(text, self._cjk_font_path)
        pdf = canvas.Canvas(str(output_path), pagesize=A4)
        width, height = A4
        x = 20 * mm
        y = height - (20 * mm)
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
                    y = height - (20 * mm)
                    pdf.setFont(font_name, font_size)
                pdf.drawString(x, y, chunk)
                y -= line_height
        pdf.save()
        return output_path

    def extract_pdf_text(self, pdf_path: Path, output_dir: Path) -> list[Path]:
        try:
            import fitz
        except ImportError as exc:
            raise DocumentRenderError("PyMuPDF is required for PDF text extraction.") from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        try:
            with fitz.open(pdf_path) as document:
                for index, page in enumerate(document, start=1):
                    output_path = output_dir / f"{index:04d}.txt"
                    output_path.write_text(page.get_text("text"), encoding="utf-8")
                    paths.append(output_path)
        except Exception as exc:
            raise DocumentRenderError(f"PDF text extraction failed: {pdf_path}") from exc
        return paths

    def render_pdf_pages(
        self,
        pdf_path: Path,
        output_dir: Path,
        page_numbers: list[int],
    ) -> list[Path]:
        try:
            import fitz
        except ImportError as exc:
            raise DocumentRenderError("PyMuPDF is required for PDF page rendering.") from exc

        selected_pages = sorted(set(page_numbers))
        if any(page_number < 1 for page_number in selected_pages):
            raise DocumentRenderError("PDF page numbers must start from 1.")
        if not selected_pages:
            return []

        output_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        previous_display_errors = fitz.TOOLS.mupdf_display_errors(False)
        try:
            try:
                with fitz.open(pdf_path) as document:
                    page_count = len(document)
                    invalid_pages = [
                        page_number for page_number in selected_pages if page_number > page_count
                    ]
                    if invalid_pages:
                        raise DocumentRenderError(
                            "Requested page is outside PDF page range "
                            f"(page_count={page_count}, requested={invalid_pages})."
                        )
                    for page_number in selected_pages:
                        page = document[page_number - 1]
                        output_path = output_dir / f"{page_number:04d}.png"
                        page.get_pixmap(dpi=self._dpi).save(output_path)
                        paths.append(output_path)
            except DocumentRenderError:
                raise
            except Exception as exc:
                raise DocumentRenderError(f"PDF page rendering failed: {pdf_path}") from exc
        finally:
            fitz.TOOLS.mupdf_display_errors(previous_display_errors)
        return paths

    def _render_image(self, image_path: Path, output_dir: Path) -> list[Path]:
        try:
            from PIL import Image
        except ImportError as exc:
            raise DocumentRenderError("Pillow is required for image page rendering.") from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "0001.png"
        with Image.open(image_path) as image:
            image.convert("RGB").save(output_path, format="PNG")
        return [output_path]


def _text_pdf_font_name(text: str, cjk_font_path: Path | None) -> str:
    if not _has_cjk_text(text):
        return "Helvetica"

    if cjk_font_path is None:
        raise DocumentRenderError("CJK TXT/MD conversion requires KBSEARCH_CJK_FONT_PATH.")

    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError as exc:
        raise DocumentRenderError("reportlab is required for CJK TXT/MD conversion.") from exc

    if CJK_TEXT_FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return CJK_TEXT_FONT_NAME

    if cjk_font_path.exists():
        try:
            pdfmetrics.registerFont(TTFont(CJK_TEXT_FONT_NAME, str(cjk_font_path)))
            return CJK_TEXT_FONT_NAME
        except Exception as exc:
            raise DocumentRenderError(f"Unable to register CJK font: {cjk_font_path}") from exc

    raise DocumentRenderError(f"CJK font file not found: {cjk_font_path}")


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


def parse_page_numbers(value: str) -> list[int]:
    if not value or value.strip() == "":
        raise DocumentRenderError("Page selection must not be empty.")

    pages: set[int] = set()
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            raise DocumentRenderError(f"Invalid page selection: {value}")
        if "-" in part:
            bounds = part.split("-")
            if len(bounds) != 2 or not all(bound.isdigit() for bound in bounds):
                raise DocumentRenderError(f"Invalid page range: {part}")
            start, end = (int(bound) for bound in bounds)
            if start < 1 or end < start:
                raise DocumentRenderError(f"Invalid page range: {part}")
            pages.update(range(start, end + 1))
        else:
            if not part.isdigit() or int(part) < 1:
                raise DocumentRenderError(f"Invalid page number: {part}")
            pages.add(int(part))
    return sorted(pages)
