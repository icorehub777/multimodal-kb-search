from __future__ import annotations

from typing import Protocol

from app.models import QueryImage, VectorFileSearchResult


class QueryEmbedder(Protocol):
    def embed_query(self, query: str, images: list[QueryImage]) -> list[float]:
        raise NotImplementedError


class VectorSearcher(Protocol):
    def search_pages(
        self,
        vector: list[float],
        limit: int,
        min_score: float | None = None,
    ) -> list[VectorFileSearchResult]:
        raise NotImplementedError


class VectorSearchService:
    def __init__(self, embedder: QueryEmbedder, searcher: VectorSearcher) -> None:
        self._embedder = embedder
        self._searcher = searcher

    def search(
        self,
        query: str,
        images: list[QueryImage],
        limit: int,
        min_score: float | None,
    ) -> list[VectorFileSearchResult]:
        vector = self._embedder.embed_query(query, images)
        return self._searcher.search_pages(vector=vector, limit=limit, min_score=min_score)
