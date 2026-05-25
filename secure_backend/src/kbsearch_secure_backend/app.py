from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException

from kbsearch_secure_backend.config import ConfigError, load_backend_config
from kbsearch_secure_backend.errors import BackendError
from kbsearch_secure_backend.factories import create_vector_search_service
from kbsearch_secure_backend.logging_config import LOGGER_NAME, configure_backend_logging
from kbsearch_secure_backend.models import VectorSearchRequest, VectorSearchResponse
from kbsearch_secure_backend.service import VectorSearchService


def create_app(service: VectorSearchService | None = None, log_file_path: Path | None = None) -> FastAPI:
    app = FastAPI(title="KBSearch Secure Backend")
    config = None
    if service is None:
        config = load_backend_config()
        if log_file_path is None:
            log_file_path = config.log_file_path
    if log_file_path is not None:
        configure_backend_logging(log_file_path)
    logger = logging.getLogger(LOGGER_NAME)
    vector_service = service or create_vector_search_service(config)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/search/vector", response_model=VectorSearchResponse)
    def search_vector(request: VectorSearchRequest) -> VectorSearchResponse:
        logger.info(
            "search_vector started query_length=%s image_count=%s limit=%s min_score=%s",
            len(request.query),
            len(request.images),
            request.limit,
            request.min_score,
        )
        try:
            response = VectorSearchResponse(
                results=vector_service.search(
                    query=request.query,
                    images=request.images,
                    limit=request.limit,
                    min_score=request.min_score,
                )
            )
            logger.info("search_vector succeeded result_count=%s limit=%s", len(response.results), request.limit)
            return response
        except (ConfigError, BackendError, RuntimeError) as exc:
            logger.exception("search_vector failed error=%s", exc.__class__.__name__)
            raise HTTPException(
                status_code=500,
                detail={"error": exc.__class__.__name__, "message": str(exc)},
            ) from exc

    return app
