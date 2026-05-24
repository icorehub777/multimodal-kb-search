from __future__ import annotations

from pathlib import Path


class UnsupportedDocumentTypeError(ValueError):
    """Raised when importer receives a document type outside the supported set."""


_MIME_TYPE_TO_DOCUMENT_TYPE = {
    "application/pdf": "pdf",
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

_EXCEL_MIME_TYPES = {
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.google-apps.spreadsheet",
}


def classify_document_type(mime_type: str) -> str:
    if mime_type in _EXCEL_MIME_TYPES:
        raise UnsupportedDocumentTypeError(
            "Excel files are not directly vectorized. Convert the file to A4 PDF first."
        )

    document_type = _MIME_TYPE_TO_DOCUMENT_TYPE.get(mime_type)
    if document_type is None:
        raise UnsupportedDocumentTypeError(f"Unsupported document MIME type: {mime_type}")

    return document_type


def page_png_path(page_dir: Path, page_number: int) -> Path:
    if page_number < 1:
        raise ValueError("page_number must be >= 1")
    return page_dir / f"{page_number:02d}.png"
