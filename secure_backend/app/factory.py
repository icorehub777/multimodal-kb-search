from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.config import BackendConfig, ConfigError, load_backend_config
from app.errors import BackendError
from app.factories import create_vector_search_service
from app.logging_config import LOGGER_NAME, configure_backend_logging
from app.models import VectorSearchRequest, VectorSearchResponse
from app.service import VectorSearchService
from app.startup_probe import probe_startup_environment


def create_app(
    service: VectorSearchService | None = None,
    log_file_path: Path | None = None,
    *,
    skip_startup_probe: bool = False,
) -> FastAPI:
    app = FastAPI(title="KBSearch Secure Backend")
    config = None
    if service is None:
        config = load_backend_config()

    effective_log_path = log_file_path
    if effective_log_path is None and config is not None:
        effective_log_path = config.log_file_path
    if effective_log_path is not None:
        configure_backend_logging(effective_log_path)

    logger = logging.getLogger(LOGGER_NAME)
    vector_service = service
    if vector_service is None:
        assert config is not None
        if not skip_startup_probe:
            _run_startup_probe(config, logger)
        vector_service = create_vector_search_service(config)

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
            logger.exception(
                "search_vector failed error=%s message=%s query_length=%s image_count=%s limit=%s min_score=%s",
                exc.__class__.__name__,
                exc,
                len(request.query),
                len(request.images),
                request.limit,
                request.min_score,
            )
            raise HTTPException(
                status_code=500,
                detail={"error": exc.__class__.__name__, "message": str(exc)},
            ) from exc

    return app


def _run_startup_probe(config: BackendConfig, logger: logging.Logger) -> None:
    logger.info(
        "startup_probe started dashscope_model=%s dashscope_vector_size=%s qdrant_collection=%s qdrant_vector_size=%s",
        config.dashscope_embedding_model,
        config.dashscope_vector_size,
        config.qdrant_collection,
        config.qdrant_vector_size,
    )
    try:
        result = probe_startup_environment(config)
    except Exception as exc:
        logger.exception(
            "startup_probe failed error=%s message=%s dashscope_model=%s qdrant_collection=%s",
            exc.__class__.__name__,
            exc,
            config.dashscope_embedding_model,
            config.qdrant_collection,
        )
        raise
    logger.info(
        "startup_probe succeeded dashscope_model=%s dashscope_dimension=%s "
        "qdrant_host=%s qdrant_collection=%s qdrant_points=%s qdrant_vector_size=%s",
        result.dashscope_model,
        result.dashscope_dimension,
        result.qdrant_host,
        result.qdrant_collection,
        result.qdrant_points_count,
        result.qdrant_vector_size,
    )
