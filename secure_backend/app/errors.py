from __future__ import annotations


class BackendError(RuntimeError):
    """Base domain error for secure backend failures."""


class ConfigError(BackendError):
    """Raised when backend configuration is missing or invalid."""


class ExternalServiceError(BackendError):
    """Raised when an external service call fails."""


class VectorSearchError(BackendError):
    """Raised when vector search cannot be completed."""
