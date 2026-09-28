from __future__ import annotations

from io import BytesIO
from http import HTTPStatus
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

from app.embedding import validate_embedding_vector
from app.errors import ExternalServiceError
from app.logging_config import LOGGER_NAME


class ImageEmbeddingClient(Protocol):
    def embed_image(self, image_path: Path) -> list[float]:
        raise NotImplementedError


class DashScopeImageEmbeddingClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        dimension: int,
        image_max_bytes: int,
        jpeg_quality: int,
        logger: logging.Logger | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._dimension = dimension
        self._image_max_bytes = image_max_bytes
        self._jpeg_quality = jpeg_quality
        self._logger = logger or logging.getLogger(LOGGER_NAME)

    def embed_image(self, image_path: Path) -> list[float]:
        try:
            import dashscope
            from dashscope import MultiModalEmbedding
        except ImportError as exc:
            raise RuntimeError("dashscope is required for embedding operations.") from exc

        dashscope.api_key = self._api_key
        with TemporaryDirectory(prefix="kbsearch-dashscope-") as temp_dir:
            prepared_path = _prepare_image_for_dashscope(
                image_path,
                max_bytes=self._image_max_bytes,
                jpeg_quality=self._jpeg_quality,
                output_dir=Path(temp_dir),
                logger=self._logger,
            )
            try:
                response = MultiModalEmbedding.call(
                    model=self._model,
                    input=[{"image": str(prepared_path.resolve())}],
                    api_key=self._api_key,
                    timeout=120,
                )
            except Exception as exc:
                raise ExternalServiceError(
                    f"DashScope embedding request failed (model={self._model})."
                ) from exc
        status_code = getattr(response, "status_code", None)
        if not isinstance(status_code, int):
            raise ExternalServiceError("DashScope embedding returned an invalid response status.")
        if status_code != HTTPStatus.OK:
            code = getattr(response, "code", "") or ""
            message = getattr(response, "message", "") or str(response)
            raise ExternalServiceError(
                f"DashScope embedding failed (HTTP {status_code}): {code} {message}".strip()
            )

        output = getattr(response, "output", None)
        embeddings = output.get("embeddings") if isinstance(output, dict) else None
        if not isinstance(embeddings, list) or not embeddings:
            raise ExternalServiceError("DashScope embedding response does not contain embeddings.")
        first_embedding = embeddings[0]
        vector = first_embedding.get("embedding") if isinstance(first_embedding, dict) else None
        if not isinstance(vector, (list, tuple)) or not vector:
            raise ExternalServiceError("DashScope embedding response does not contain a vector.")
        try:
            return list(validate_embedding_vector(list(vector), self._dimension))
        except (TypeError, ValueError) as exc:
            raise ExternalServiceError(
                f"DashScope embedding response contains an invalid vector (model={self._model})."
            ) from exc


class DashScopePageEmbedder:
    def __init__(self, client: ImageEmbeddingClient, expected_dimension: int) -> None:
        self._client = client
        self._expected_dimension = expected_dimension

    def embed_page_image(self, image_path: Path) -> list[float]:
        vector = self._client.embed_image(image_path)
        return list(validate_embedding_vector(vector, self._expected_dimension))


def _prepare_image_for_dashscope(
    image_path: Path,
    *,
    max_bytes: int,
    jpeg_quality: int,
    output_dir: Path,
    logger: logging.Logger | None = None,
) -> Path:
    source_bytes = image_path.stat().st_size
    if source_bytes <= max_bytes:
        return image_path

    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required to compress large images for DashScope.") from exc

    active_logger = logger or logging.getLogger(LOGGER_NAME)
    with Image.open(image_path) as source_image:
        image = source_image.convert("RGB")
    original_size = image.size
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{image_path.stem}.jpg"
    quality_levels = tuple(range(jpeg_quality, 39, -5)) or (jpeg_quality,)

    for _attempt in range(12):
        for quality in quality_levels:
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=quality, optimize=True)
            payload = buffer.getvalue()
            if len(payload) <= max_bytes:
                output_path.write_bytes(payload)
                active_logger.info(
                    "embedding_image_prepared source=%s original_width=%s original_height=%s "
                    "original_bytes=%s final_width=%s final_height=%s final_bytes=%s "
                    "format=jpeg quality=%s max_bytes=%s",
                    image_path,
                    original_size[0],
                    original_size[1],
                    source_bytes,
                    image.width,
                    image.height,
                    len(payload),
                    quality,
                    max_bytes,
                )
                return output_path

        width, height = image.size
        next_size = (max(1, int(width * 0.85)), max(1, int(height * 0.85)))
        if next_size == image.size:
            break
        image = image.resize(next_size, Image.Resampling.LANCZOS)

    raise RuntimeError(
        f"Unable to compress image under DashScope size limit ({max_bytes} bytes): {image_path}"
    )
