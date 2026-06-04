from __future__ import annotations


class ImporterError(RuntimeError):
    """Base domain error for importer failures."""


class ExternalServiceError(ImporterError):
    """Raised when an external service call fails."""


class DocumentConversionError(ImporterError):
    """Raised when document conversion fails."""


class DocumentImportError(ImporterError):
    """Raised when a document cannot be imported as a complete unit."""
