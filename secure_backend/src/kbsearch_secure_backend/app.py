from __future__ import annotations

from fastapi import FastAPI, HTTPException

from kbsearch_secure_backend.config import ConfigError, load_backend_config
from kbsearch_secure_backend.errors import BackendError
from kbsearch_secure_backend.factories import create_vector_search_service
from kbsearch_secure_backend.models import VectorSearchRequest, VectorSearchResponse
from kbsearch_secure_backend.service import VectorSearchService


def create_app(service: VectorSearchService | None = None) -> FastAPI:
    app = FastAPI(title="KBSearch Secure Backend")
    vector_service = service or create_vector_search_service(load_backend_config())

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/search/vector", response_model=VectorSearchResponse)
    def search_vector(request: VectorSearchRequest) -> VectorSearchResponse:
        try:
            return VectorSearchResponse(
                results=vector_service.search(
                    query=request.query,
                    images=request.images,
                    limit=request.limit,
                    min_score=request.min_score,
                )
            )
        except (ConfigError, BackendError, RuntimeError) as exc:
            raise HTTPException(
                status_code=500,
                detail={"error": exc.__class__.__name__, "message": str(exc)},
            ) from exc

    return app
