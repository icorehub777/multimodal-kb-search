from __future__ import annotations


class QueryCliError(RuntimeError):
    """Base domain error for query CLI failures."""


class ConfigError(QueryCliError):
    """Raised when query CLI configuration is missing or invalid."""


class ExternalServiceError(QueryCliError):
    """Raised when Google Drive or secure backend calls fail."""


class DocumentRenderError(QueryCliError):
    """Raised when a downloaded document cannot be rendered to page images."""
