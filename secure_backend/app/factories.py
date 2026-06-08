from __future__ import annotations

from app.config import BackendConfig
from app.embedding import DashScopeQueryEmbeddingClient
from app.qdrant_client_factory import build_qdrant_client
from app.qdrant_search import QdrantSearchAdapter
from app.service import VectorSearchService


def create_vector_search_service(config: BackendConfig) -> VectorSearchService:
    return VectorSearchService(
        embedder=DashScopeQueryEmbeddingClient(
            api_key=config.dashscope_api_key,
            model=config.dashscope_embedding_model,
            dimension=config.dashscope_vector_size,
        ),
        searcher=QdrantSearchAdapter(
            client=build_qdrant_client(config.qdrant_url, config.qdrant_api_key),
            collection=config.qdrant_collection,
        ),
    )
