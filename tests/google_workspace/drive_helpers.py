"""Drive API 共用常數與小工具。"""

from __future__ import annotations

GOOGLE_NATIVE_MIMES = frozenset(
    {
        "application/vnd.google-apps.document",
        "application/vnd.google-apps.spreadsheet",
        "application/vnd.google-apps.presentation",
    }
)

EXPORT_TARGET_PDF = "application/pdf"

FILE_METADATA_FIELDS = (
    "id,name,mimeType,parents,webViewLink,version,modifiedTime,trashed,size"
)


def is_google_native(mime_type: str) -> bool:
    return mime_type in GOOGLE_NATIVE_MIMES


def escape_query_term(term: str) -> str:
    """Drive q 參數內單引號跳脫。"""
    return term.replace("\\", "\\\\").replace("'", "\\'")
