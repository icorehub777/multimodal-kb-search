from __future__ import annotations

import hmac
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader

from kbsearch_backend.config import BackendConfig, load_backend_config
from kbsearch_backend.errors import (
    AuthenticationError,
    BackendError,
    ExternalServiceError,
    InvalidRequestError,
    PayloadTooLargeError,
)
from kbsearch_backend.factories import create_vector_search_service
from kbsearch_backend.logging_config import LOGGER_NAME, configure_backend_logging
from kbsearch_backend.models import ErrorResponse, VectorSearchRequest, VectorSearchResponse
from kbsearch_backend.service import VectorSearchService
from kbsearch_backend.startup_probe import probe_startup_environment


def create_app(
    service: VectorSearchService | None = None,
    log_file_path: Path | None = None,
    *,
    config: BackendConfig | None = None,
    skip_startup_probe: bool = False,
) -> FastAPI:
    effective_config = config or load_backend_config()
    effective_log_path = log_file_path or effective_config.log_file_path
    logger = configure_backend_logging(effective_log_path, effective_config.log_level)

    vector_service = service
    if vector_service is None:
        if not skip_startup_probe:
            _run_startup_probe(effective_config, logger)
        vector_service = create_vector_search_service(effective_config)

    app = FastAPI(title="KBSearch Secure Backend")
    _register_exception_handlers(app, logger)
    api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

    def require_api_key(provided_api_key: str | None = Depends(api_key_header)) -> None:
        if provided_api_key is None or not hmac.compare_digest(
            provided_api_key,
            effective_config.secure_backend_api_key,
        ):
            raise AuthenticationError("API key is missing or invalid.")

    authentication = [Depends(require_api_key)]

    @app.get(
        "/healthz",
        dependencies=authentication,
        responses={401: {"model": ErrorResponse}},
    )
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/search/vector",
        response_model=VectorSearchResponse,
        dependencies=authentication,
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            413: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
        },
    )
    def search_vector(request: VectorSearchRequest) -> VectorSearchResponse:
        query = request.query.strip()
        _validate_search_request(request, query, effective_config)
        logger.info(
            "search_vector started query_length=%s image_count=%s limit=%s min_score=%s",
            len(query),
            len(request.images),
            request.limit,
            request.min_score,
        )
        response = VectorSearchResponse(
            results=vector_service.search(
                query=query,
                images=request.images,
                limit=request.limit,
                min_score=request.min_score,
            )
        )
        logger.info(
            "search_vector succeeded result_count=%s limit=%s",
            len(response.results),
            request.limit,
        )
        return response

    return app


def _validate_search_request(
    request: VectorSearchRequest,
    query: str,
    config: BackendConfig,
) -> None:
    if not query and not request.images:
        raise InvalidRequestError(
            "query or images must be provided.",
            field="query",
        )
    if len(query) > config.max_query_length:
        raise InvalidRequestError(
            f"query must not exceed {config.max_query_length} characters.",
            field="query",
        )
    if len(request.images) > config.max_images:
        raise InvalidRequestError(
            f"images must contain at most {config.max_images} item(s).",
            field="images",
        )
    if request.limit > config.max_search_limit:
        raise InvalidRequestError(
            f"limit must be between 1 and {config.max_search_limit}.",
            field="limit",
        )


def _register_exception_handlers(app: FastAPI, logger: logging.Logger) -> None:
    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(
        _request: Request,
        exc: AuthenticationError,
    ) -> JSONResponse:
        logger.warning("request rejected error=authentication")
        return _error_response(401, "authentication", str(exc))

    @app.exception_handler(InvalidRequestError)
    async def invalid_request_error_handler(
        _request: Request,
        exc: InvalidRequestError,
    ) -> JSONResponse:
        status_code = 413 if isinstance(exc, PayloadTooLargeError) else 400
        error_code = "payload_too_large" if status_code == 413 else "invalid_request"
        logger.warning(
            "request rejected error=%s field=%s message=%s",
            error_code,
            exc.field,
            exc,
        )
        return _error_response(status_code, error_code, str(exc), field=exc.field)

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        field, message = _request_validation_detail(exc)
        logger.warning(
            "request rejected error=invalid_request field=%s message=%s",
            field,
            message,
        )
        return _error_response(400, "invalid_request", message, field=field)

    @app.exception_handler(ExternalServiceError)
    async def external_service_error_handler(
        _request: Request,
        exc: ExternalServiceError,
    ) -> JSONResponse:
        logger.error("request failed error=external_service message=%s", exc, exc_info=exc)
        return _error_response(502, "external_service", "An external service request failed.")

    @app.exception_handler(BackendError)
    async def backend_error_handler(_request: Request, exc: BackendError) -> JSONResponse:
        logger.error("request failed error=internal message=%s", exc, exc_info=exc)
        return _error_response(500, "internal", "An internal error occurred.")

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "request failed error=internal exception=%s message=%s",
            exc.__class__.__name__,
            exc,
            exc_info=exc,
        )
        return _error_response(500, "internal", "An internal error occurred.")


def _request_validation_detail(exc: RequestValidationError) -> tuple[str | None, str]:
    first_error = exc.errors()[0] if exc.errors() else {}
    location = first_error.get("loc", ())
    field = str(location[-1]) if location else None
    if field == "min_score":
        return field, "min_score must be a finite number between -1 and 1."
    if field == "limit":
        return field, "limit must be a positive integer."
    if field in {"filename", "mime_type", "base64_data"}:
        return "images", f"images contains an invalid {field}."
    return field, f"{field or 'request'} is invalid."


def _error_response(
    status_code: int,
    error: str,
    message: str,
    *,
    field: str | None = None,
) -> JSONResponse:
    content = {"error": error, "message": message}
    if field is not None:
        content["field"] = field
    return JSONResponse(status_code=status_code, content=content)


def _run_startup_probe(config: BackendConfig, logger: logging.Logger) -> None:
    logger.info(
        "startup_probe started dashscope_model=%s vector_size=%s "
        "qdrant_collection=%s",
        config.dashscope_embedding_model,
        config.vector_size,
        config.qdrant_collection,
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
