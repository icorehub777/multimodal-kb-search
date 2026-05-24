from __future__ import annotations

import subprocess
from pathlib import Path

from kbsearch_cli.errors import DocumentRenderError

CJK_TEXT_FONT_NAME = "KBSearchTextCJK"


class DocumentPageRenderer:
    def __init__(
        self,
        libreoffice_command: str = "soffice",
        cjk_font_path: Path | None = None,
        dpi: int = 200,
    ) -> None:
        self._libreoffice_command = libreoffice_command
        self._cjk_font_path = cjk_font_path
        self._dpi = dpi

    def render_pages(self, source_path: Path, output_dir: Path) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        render_source = self._render_source_path(source_path, output_dir)
        if render_source.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            return self._render_image(render_source, output_dir)
        return self._render_pdf(render_source, output_dir)

    def _render_source_path(self, source_path: Path, output_dir: Path) -> Path:
        suffix = source_path.suffix.lower()
        if suffix in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
            return source_path
        if suffix in {".doc", ".docx", ".ppt", ".pptx"}:
            return self._convert_office_to_pdf(source_path, output_dir)
        if suffix in {".txt", ".md"}:
            return self._convert_text_to_pdf(source_path, output_dir)
        raise DocumentRenderError(f"Unsupported document extension: {source_path.suffix}")

    def _convert_office_to_pdf(self, source_path: Path, output_dir: Path) -> Path:
        try:
            result = subprocess.run(
                [
                    self._libreoffice_command,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(output_dir),
                    str(source_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise DocumentRenderError(f"Office to PDF conversion failed: {source_path}") from exc
        if result.returncode != 0:
            raise DocumentRenderError(
                f"Office to PDF conversion failed for {source_path}: {result.stderr.strip()}"
            )
        output_path = output_dir / f"{source_path.stem}.pdf"
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

    def _render_pdf(self, pdf_path: Path, output_dir: Path) -> list[Path]:
        try:
            import fitz
        except ImportError as exc:
            raise DocumentRenderError("PyMuPDF is required for PDF page rendering.") from exc

        paths: list[Path] = []
        with fitz.open(pdf_path) as document:
            for index, page in enumerate(document, start=1):
                output_path = output_dir / f"{index:02d}.png"
                page.get_pixmap(dpi=self._dpi).save(output_path)
                paths.append(output_path)
        return paths

    def _render_image(self, image_path: Path, output_dir: Path) -> list[Path]:
        try:
            from PIL import Image
        except ImportError as exc:
            raise DocumentRenderError("Pillow is required for image page rendering.") from exc

        output_path = output_dir / "01.png"
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
