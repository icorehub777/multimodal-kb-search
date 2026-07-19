from __future__ import annotations


class BackendError(RuntimeError):
    """Base domain error for secure backend failures."""


class ConfigError(BackendError):
    """Raised when backend configuration is missing or invalid."""


class InvalidRequestError(BackendError):
    """Raised when a request payload is well-formed JSON but semantically invalid."""


class ExternalServiceError(BackendError):
    """Raised when an external service call fails."""


class VectorSearchError(BackendError):
    """Raised when vector search cannot be completed."""
