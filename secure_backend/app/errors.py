from __future__ import annotations


class BackendError(RuntimeError):
    """Base domain error for secure backend failures."""


class ConfigError(BackendError):
    """Raised when backend configuration is missing or invalid."""


class InvalidRequestError(BackendError):
    """Raised when a request payload is well-formed JSON but semantically invalid."""

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class PayloadTooLargeError(InvalidRequestError):
    """Raised when a request payload exceeds service processing limits."""


class ExternalServiceError(BackendError):
    """Raised when an external service call fails."""


class AuthenticationError(BackendError):
    """Raised when the caller does not provide the configured API key."""


class VectorSearchError(BackendError):
    """Raised when vector search cannot be completed."""
