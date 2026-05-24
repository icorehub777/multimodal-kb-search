from __future__ import annotations

import base64
import binascii
from http import HTTPStatus
from io import BytesIO
from typing import Protocol

from kbsearch_secure_backend.errors import ExternalServiceError
from kbsearch_secure_backend.models import QueryImage

MAX_DASHSCOPE_IMAGE_BYTES = 5_070 * 1024


class QueryEmbeddingClient(Protocol):
    def embed_query(self, query: str, images: list[QueryImage]) -> list[float]:
        raise NotImplementedError


class DashScopeQueryEmbeddingClient:
    def __init__(self, api_key: str, model: str, dimension: int) -> None:
        self._api_key = api_key
        self._model = model
        self._dimension = dimension

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
        inputs.extend({"image": _image_data_uri_from_payload(image)} for image in images)
        if not inputs:
            raise ExternalServiceError("Vector search requires query text or at least one image.")

        response = MultiModalEmbedding.call(
            model=self._model,
            input=inputs,
            api_key=self._api_key,
        )
        if response.status_code != HTTPStatus.OK:
            code = getattr(response, "code", "") or ""
            message = getattr(response, "message", "") or str(response)
            raise ExternalServiceError(
                f"DashScope embedding failed (HTTP {response.status_code}): {code} {message}".strip()
            )

        embeddings = (response.output or {}).get("embeddings") or []
        if not embeddings:
            raise ExternalServiceError("DashScope embedding response does not contain embeddings.")
        vector = embeddings[0].get("embedding")
        if not vector:
            raise ExternalServiceError("DashScope embedding response does not contain a vector.")
        return validate_embedding_vector(list(vector), self._dimension)


def validate_embedding_vector(vector: list[float], expected_dimension: int) -> list[float]:
    if len(vector) != expected_dimension:
        raise ExternalServiceError(
            f"Embedding vector dimension mismatch: expected {expected_dimension}, got {len(vector)}."
        )
    return vector


def _image_data_uri_from_payload(image: QueryImage) -> str:
    base64_data = image.base64_data.strip()
    try:
        image_bytes = base64.b64decode(base64_data, validate=True)
    except binascii.Error as exc:
        raise ExternalServiceError(f"Invalid base64 image payload: {image.filename}") from exc

    if len(image_bytes) <= MAX_DASHSCOPE_IMAGE_BYTES:
        return f"data:{image.mime_type};base64,{base64_data}"

    compressed = _compress_image_bytes_for_dashscope(image_bytes)
    encoded = base64.b64encode(compressed).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _compress_image_bytes_for_dashscope(image_bytes: bytes) -> bytes:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required to compress large images for DashScope.") from exc

    with Image.open(BytesIO(image_bytes)) as source_image:
        image = source_image.convert("RGB")

    for _attempt in range(12):
        for quality in (85, 75, 65, 55, 45):
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=quality, optimize=True)
            payload = buffer.getvalue()
            if len(payload) <= MAX_DASHSCOPE_IMAGE_BYTES:
                return payload

        width, height = image.size
        next_size = (max(1, int(width * 0.85)), max(1, int(height * 0.85)))
        if next_size == image.size:
            break
        image = image.resize(next_size)

    raise RuntimeError("Unable to compress image under DashScope size limit.")
