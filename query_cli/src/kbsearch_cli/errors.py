from __future__ import annotations


class QueryCliError(RuntimeError):
    """Base domain error for query CLI failures."""


class ConfigError(QueryCliError):
    """Raised when query CLI configuration is missing or invalid."""


class QueryInputError(QueryCliError):
    """Raised when command input is invalid."""


class AuthenticationError(QueryCliError):
    """Raised when interactive authentication is required."""


class ExternalServiceError(QueryCliError):
    """Raised when Google Drive or secure backend calls fail."""


class DocumentRenderError(QueryCliError):
    """Raised when a downloaded document cannot be rendered to page images."""
