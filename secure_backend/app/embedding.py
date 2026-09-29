from __future__ import annotations

import base64
import binascii
import math
from http import HTTPStatus
from io import BytesIO
from typing import Protocol

from app.errors import ExternalServiceError, InvalidRequestError, PayloadTooLargeError
from app.models import QueryImage


DASHSCOPE_REQUEST_TIMEOUT_SECONDS = 120


class QueryEmbeddingClient(Protocol):
    def embed_query(self, query: str, images: list[QueryImage]) -> list[float]:
        raise NotImplementedError


class DashScopeQueryEmbeddingClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        dimension: int,
        image_max_bytes: int,
        jpeg_quality: int,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._dimension = dimension
        self._image_max_bytes = image_max_bytes
        self._jpeg_quality = jpeg_quality

    def embed_query(self, query: str, images: list[QueryImage]) -> list[float]:
        try:
            import dashscope
            from dashscope import MultiModalEmbedding
        except ImportError as exc:
            raise RuntimeError("dashscope is required for embedding operations.") from exc

        dashscope.api_key = self._api_key
        inputs: list[dict[str, str]] = []
        if query.strip():
            inputs.append({"text": query.strip()})
        inputs.extend(
            {
                "image": _image_data_uri_from_payload(
                    image,
                    max_bytes=self._image_max_bytes,
                    jpeg_quality=self._jpeg_quality,
                )
            }
            for image in images
        )
        if not inputs:
            raise ExternalServiceError("Vector search requires query text or at least one image.")

        try:
            response = MultiModalEmbedding.call(
                model=self._model,
                input=inputs,
                api_key=self._api_key,
                timeout=DASHSCOPE_REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            raise ExternalServiceError("DashScope embedding request failed.") from exc
        if response.status_code != HTTPStatus.OK:
            code = getattr(response, "code", "") or ""
            message = getattr(response, "message", "") or str(response)
            detail = RuntimeError(
                f"DashScope embedding failed (HTTP {response.status_code}): {code} {message}".strip()
            )
            raise ExternalServiceError("DashScope embedding request failed.") from detail

        try:
            output = response.output
            if not isinstance(output, dict):
                raise TypeError("output must be an object")
            embeddings = output.get("embeddings")
            if not isinstance(embeddings, list) or not embeddings:
                raise TypeError("embeddings must be a non-empty array")
            first_embedding = embeddings[0]
            if not isinstance(first_embedding, dict):
                raise TypeError("embedding item must be an object")
            vector = first_embedding.get("embedding")
            if not isinstance(vector, list):
                raise TypeError("embedding must be an array")
            return validate_embedding_vector(vector, self._dimension)
        except (TypeError, ValueError) as exc:
            raise ExternalServiceError("DashScope returned an invalid response.") from exc


def validate_embedding_vector(vector: list[float], expected_dimension: int) -> list[float]:
    if len(vector) != expected_dimension:
        raise ExternalServiceError(
            f"Embedding vector dimension mismatch: expected {expected_dimension}, got {len(vector)}."
        )
    normalized: list[float] = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Embedding vector values must be numbers.")
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("Embedding vector values must be finite.")
        normalized.append(parsed)
    return normalized


def _image_data_uri_from_payload(
    image: QueryImage,
    *,
    max_bytes: int,
    jpeg_quality: int,
) -> str:
    base64_data = image.base64_data.strip()
    try:
        image_bytes = base64.b64decode(base64_data, validate=True)
    except binascii.Error as exc:
        raise InvalidRequestError(
            f"Invalid base64 image payload: {image.filename}", field="images"
        ) from exc

    try:
        normalized = _normalize_image_bytes_for_dashscope(image_bytes)
    except OSError as exc:
        raise InvalidRequestError(f"Invalid image payload: {image.filename}", field="images") from exc
    if len(normalized) <= max_bytes:
        encoded = base64.b64encode(normalized).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    try:
        compressed = _compress_image_bytes_for_dashscope(
            normalized,
            max_bytes=max_bytes,
            jpeg_quality=jpeg_quality,
        )
    except PayloadTooLargeError as exc:
        raise PayloadTooLargeError(
            f"Image payload exceeds DashScope image size limit: {image.filename} "
            f"(max_bytes={max_bytes}).",
            field="images",
        ) from exc
    except OSError as exc:
        raise InvalidRequestError(f"Invalid image payload: {image.filename}", field="images") from exc
    encoded = base64.b64encode(compressed).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _normalize_image_bytes_for_dashscope(image_bytes: bytes) -> bytes:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow is required to normalize images for DashScope.") from exc

    # PNG does not inherently improve embedding quality. It mirrors importer's
    # page-image conversion so indexed and query images receive the same pixel,
    # color-mode, and EXIF-orientation normalization before embedding.
    with Image.open(BytesIO(image_bytes)) as source_image:
        image = ImageOps.exif_transpose(source_image).convert("RGB")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _compress_image_bytes_for_dashscope(
    image_bytes: bytes,
    *,
    max_bytes: int,
    jpeg_quality: int,
) -> bytes:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow is required to compress large images for DashScope.") from exc

    with Image.open(BytesIO(image_bytes)) as source_image:
        image = ImageOps.exif_transpose(source_image).convert("RGB")

    quality_levels = tuple(range(jpeg_quality, 39, -5)) or (jpeg_quality,)
    for _attempt in range(12):
        for quality in quality_levels:
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=quality, optimize=True)
            payload = buffer.getvalue()
            if len(payload) <= max_bytes:
                return payload

        width, height = image.size
        next_size = (max(1, int(width * 0.85)), max(1, int(height * 0.85)))
        if next_size == image.size:
            break
        image = image.resize(next_size, Image.Resampling.LANCZOS)

    raise PayloadTooLargeError(f"Unable to compress image under DashScope size limit ({max_bytes} bytes).")
