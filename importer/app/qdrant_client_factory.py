from __future__ import annotations

from typing import Any


def build_qdrant_client(url: str, api_key: str | None) -> Any:
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise RuntimeError("qdrant-client is required for Qdrant operations.") from exc

    if api_key:
        return QdrantClient(url=url, api_key=api_key)
    return QdrantClient(url=url)
