from __future__ import annotations

from kbsearch_backend.config import BackendConfig
from kbsearch_backend.embedding import DashScopeQueryEmbeddingClient
from kbsearch_backend.qdrant_client_factory import build_qdrant_client
from kbsearch_backend.qdrant_search import QdrantSearchAdapter
from kbsearch_backend.service import VectorSearchService


def create_vector_search_service(config: BackendConfig) -> VectorSearchService:
    return VectorSearchService(
        embedder=DashScopeQueryEmbeddingClient(
            api_key=config.dashscope_api_key,
            model=config.dashscope_embedding_model,
            dimension=config.vector_size,
            image_max_bytes=config.dashscope_image_max_bytes,
            jpeg_quality=config.dashscope_jpeg_quality,
        ),
        searcher=QdrantSearchAdapter(
            client=build_qdrant_client(config.qdrant_url, config.qdrant_api_key),
            collection=config.qdrant_collection,
        ),
    )
