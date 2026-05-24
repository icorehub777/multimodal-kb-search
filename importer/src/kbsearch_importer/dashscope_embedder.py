from __future__ import annotations

import base64
from io import BytesIO
from http import HTTPStatus
from pathlib import Path
from typing import Protocol

from kbsearch_importer.embedding import validate_embedding_vector

MAX_DASHSCOPE_IMAGE_BYTES = 5_070 * 1024


class ImageEmbeddingClient(Protocol):
    def embed_image(self, image_path: Path) -> list[float]:
        raise NotImplementedError


class DashScopeImageEmbeddingClient:
    def __init__(self, api_key: str, model: str, dimension: int) -> None:
        self._api_key = api_key
        self._model = model
        self._dimension = dimension

    def embed_image(self, image_path: Path) -> list[float]:
        try:
            import dashscope
            from dashscope import MultiModalEmbedding
        except ImportError as exc:
            raise RuntimeError("dashscope is required for embedding operations.") from exc

        dashscope.api_key = self._api_key
        response = MultiModalEmbedding.call(
            model=self._model,
            input=[{"image": _image_data_uri(image_path)}],
            api_key=self._api_key,
        )
        if response.status_code != HTTPStatus.OK:
            code = getattr(response, "code", "") or ""
            message = getattr(response, "message", "") or str(response)
            raise RuntimeError(
                f"DashScope embedding failed (HTTP {response.status_code}): {code} {message}".strip()
            )

        embeddings = (response.output or {}).get("embeddings") or []
        if not embeddings:
            raise RuntimeError("DashScope embedding response does not contain embeddings.")
        vector = embeddings[0].get("embedding")
        if not vector:
            raise RuntimeError("DashScope embedding response does not contain a vector.")
        return list(validate_embedding_vector(list(vector), self._dimension))


class DashScopePageEmbedder:
    def __init__(self, client: ImageEmbeddingClient, expected_dimension: int) -> None:
        self._client = client
        self._expected_dimension = expected_dimension

    def embed_page_image(self, image_path: Path) -> list[float]:
        vector = self._client.embed_image(image_path)
        return list(validate_embedding_vector(vector, self._expected_dimension))


def _image_data_uri(image_path: Path) -> str:
    image_bytes = image_path.read_bytes()
    suffix = image_path.suffix.lower()
    if len(image_bytes) <= MAX_DASHSCOPE_IMAGE_BYTES and (suffix == ".jpg" or suffix == ".jpeg"):
        mime_type = "image/jpeg"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"
    if len(image_bytes) <= MAX_DASHSCOPE_IMAGE_BYTES:
        mime_type = "image/png"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    compressed = _compress_image_for_dashscope(image_path)
    encoded = base64.b64encode(compressed).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _compress_image_for_dashscope(image_path: Path) -> bytes:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required to compress large images for DashScope.") from exc

    with Image.open(image_path) as source_image:
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

    raise RuntimeError(f"Unable to compress image under DashScope size limit: {image_path}")
