from __future__ import annotations


class EmbeddingDimensionError(ValueError):
    """Raised when an embedding vector does not match the configured dimension."""


def validate_embedding_vector(
    vector: list[float] | tuple[float, ...],
    expected_dimension: int,
) -> tuple[float, ...]:
    if len(vector) != expected_dimension:
        raise EmbeddingDimensionError(
            f"Embedding dimension mismatch: expected {expected_dimension}, got {len(vector)}."
        )
    return tuple(vector)
