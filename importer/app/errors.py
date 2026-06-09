from __future__ import annotations

from dataclasses import dataclass


class ImporterError(RuntimeError):
    """Base domain error for importer failures."""


class ExternalServiceError(ImporterError):
    """Raised when an external service call fails."""


class DocumentConversionError(ImporterError):
    """Raised when document conversion fails."""


@dataclass(frozen=True)
class DocumentImportFailure:
    file_id: str
    name: str
    action: str
    stage: str
    page_number: int | None
    error_type: str
    error_message: str


class DocumentImportError(ImporterError):
    """Raised when a document cannot be imported as a complete unit."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        page_number: int | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.page_number = page_number
