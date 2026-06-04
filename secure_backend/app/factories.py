from __future__ import annotations

from app.config import BackendConfig
from app.embedding import DashScopeQueryEmbeddingClient
from app.qdrant_search import QdrantSearchAdapter
from app.service import VectorSearchService


def create_vector_search_service(config: BackendConfig) -> VectorSearchService:
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise RuntimeError("qdrant-client is required for vector search operations.") from exc

    return VectorSearchService(
        embedder=DashScopeQueryEmbeddingClient(
            api_key=config.dashscope_api_key,
            model=config.dashscope_embedding_model,
            dimension=config.dashscope_vector_size,
        ),
        searcher=QdrantSearchAdapter(
            client=QdrantClient(url=config.qdrant_url, api_key=config.qdrant_api_key),
            collection=config.qdrant_collection,
        ),
    )
