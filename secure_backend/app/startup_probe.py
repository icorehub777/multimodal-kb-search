from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import BackendConfig
from app.embedding import DashScopeQueryEmbeddingClient
from app.errors import ExternalServiceError


@dataclass(frozen=True)
class StartupProbeResult:
    dashscope_model: str
    dashscope_dimension: int
    qdrant_collection: str
    qdrant_host: str
    qdrant_points_count: int
    qdrant_vector_size: int


def probe_startup_environment(config: BackendConfig) -> StartupProbeResult:
    """Verify DashScope embedding and Qdrant collection before serving traffic."""
    dashscope_dimension = _probe_dashscope(config)
    qdrant_points_count, qdrant_vector_size = _probe_qdrant(config)
    return StartupProbeResult(
        dashscope_model=config.dashscope_embedding_model,
        dashscope_dimension=dashscope_dimension,
        qdrant_collection=config.qdrant_collection,
        qdrant_host=_qdrant_host(config.qdrant_url),
        qdrant_points_count=qdrant_points_count,
        qdrant_vector_size=qdrant_vector_size,
    )


def _probe_dashscope(config: BackendConfig) -> int:
    client = DashScopeQueryEmbeddingClient(
        api_key=config.dashscope_api_key,
        model=config.dashscope_embedding_model,
        dimension=config.dashscope_vector_size,
    )
    try:
        vector = client.embed_query("kbsearch startup probe", [])
    except ExternalServiceError:
        raise
    except Exception as exc:
        raise ExternalServiceError(
            "DashScope startup probe failed "
            f"(model={config.dashscope_embedding_model}, dimension={config.dashscope_vector_size})."
        ) from exc
    return len(vector)


def _probe_qdrant(config: BackendConfig) -> tuple[int, int]:
    from app.qdrant_client_factory import build_qdrant_client

    client = build_qdrant_client(config.qdrant_url, config.qdrant_api_key)
    collection = config.qdrant_collection
    host = _qdrant_host(config.qdrant_url)

    try:
        if not client.collection_exists(collection):
            raise ExternalServiceError(
                f"Qdrant collection does not exist (host={host}, collection={collection})."
            )
        info = client.get_collection(collection)
    except ExternalServiceError:
        raise
    except Exception as exc:
        raise ExternalServiceError(
            f"Qdrant startup probe failed (host={host}, collection={collection})."
        ) from exc

    vector_size = _collection_vector_size(info, collection, host)
    if vector_size != config.qdrant_vector_size:
        raise ExternalServiceError(
            "Qdrant collection vector size mismatch "
            f"(host={host}, collection={collection}, expected={config.qdrant_vector_size}, "
            f"actual={vector_size})."
        )

    return int(info.points_count or 0), vector_size


def _collection_vector_size(info: object, collection: str, host: str) -> int:
    params = getattr(getattr(info, "config", None), "params", None)
    vectors = getattr(params, "vectors", None)
    if vectors is None:
        raise ExternalServiceError(
            f"Qdrant collection has no vector config (host={host}, collection={collection})."
        )

    size = getattr(vectors, "size", None)
    if size is not None:
        return int(size)

    if isinstance(vectors, dict):
        if len(vectors) != 1:
            raise ExternalServiceError(
                "Qdrant collection uses named vectors; secure_backend expects a single unnamed vector "
                f"(host={host}, collection={collection})."
            )
        only_vector = next(iter(vectors.values()))
        named_size = getattr(only_vector, "size", None)
        if named_size is None:
            raise ExternalServiceError(
                f"Qdrant named vector config is missing size (host={host}, collection={collection})."
            )
        return int(named_size)

    raise ExternalServiceError(
        f"Unable to read Qdrant vector size (host={host}, collection={collection})."
    )


def _qdrant_host(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc:
        return parsed.netloc
    return url
