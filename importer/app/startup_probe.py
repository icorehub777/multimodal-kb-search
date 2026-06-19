from __future__ import annotations

import base64
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

from app.config import ConfigError, ImporterConfig
from app.dashscope_embedder import DashScopeImageEmbeddingClient
from app.errors import ExternalServiceError
from app.factories import create_drive_scanner, create_qdrant_index
from app.qdrant_index import ensure_qdrant_collection

TINY_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


@dataclass(frozen=True)
class StartupProbeResult:
    google_documents: int
    dashscope_model: str
    dashscope_dimension: int
    qdrant_collection: str
    qdrant_host: str
    qdrant_documents: int
    qdrant_vector_size: int
    qdrant_collection_created: bool
    cjk_font_path: Path


def probe_startup_environment(config: ImporterConfig) -> StartupProbeResult:
    """Verify local tools and external services before running sync."""
    _probe_local_tools(config)
    google_documents = len(create_drive_scanner(config).list_documents())
    dashscope_dimension = _probe_dashscope(config)
    qdrant_documents, qdrant_vector_size, qdrant_collection_created = _probe_qdrant(config)
    return StartupProbeResult(
        google_documents=google_documents,
        dashscope_model=config.dashscope_embedding_model,
        dashscope_dimension=dashscope_dimension,
        qdrant_collection=config.qdrant_collection,
        qdrant_host=_qdrant_host(config.qdrant_url),
        qdrant_documents=qdrant_documents,
        qdrant_vector_size=qdrant_vector_size,
        qdrant_collection_created=qdrant_collection_created,
        cjk_font_path=config.cjk_font_path,
    )


def _probe_local_tools(config: ImporterConfig) -> None:
    if shutil.which("soffice") is None:
        raise ConfigError("LibreOffice command not found in PATH: soffice")
    if not config.cjk_font_path.is_file():
        raise ConfigError(f"CJK font not found: {config.cjk_font_path}")


def _probe_dashscope(config: ImporterConfig) -> int:
    client = DashScopeImageEmbeddingClient(
        api_key=config.dashscope_api_key,
        model=config.dashscope_embedding_model,
        dimension=config.dashscope_vector_size,
    )
    try:
        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "startup-probe.png"
            image_path.write_bytes(base64.b64decode(TINY_PNG_BASE64))
            vector = client.embed_image(image_path)
    except ExternalServiceError:
        raise
    except Exception as exc:
        raise ExternalServiceError(
            "DashScope startup probe failed "
            f"(model={config.dashscope_embedding_model}, dimension={config.dashscope_vector_size})."
        ) from exc
    return len(vector)


def _probe_qdrant(config: ImporterConfig) -> tuple[int, int, bool]:
    from app.qdrant_client_factory import build_qdrant_client

    client = build_qdrant_client(config.qdrant_url, config.qdrant_api_key)
    collection = config.qdrant_collection
    host = _qdrant_host(config.qdrant_url)

    try:
        collection_created = ensure_qdrant_collection(
            client,
            collection,
            config.qdrant_vector_size,
        )
        info = client.get_collection(collection)
    except ExternalServiceError:
        raise
    except Exception as exc:
        raise ExternalServiceError(
            f"Qdrant startup probe failed (host={host}, collection={collection})."
        ) from exc

    vector_size = _collection_vector_size(info, collection, host)
    if vector_size != config.qdrant_vector_size:
        raise ExternalServiceError(
            "Qdrant collection vector size mismatch "
            f"(host={host}, collection={collection}, expected={config.qdrant_vector_size}, "
            f"actual={vector_size})."
        )

    qdrant_documents = len(create_qdrant_index(config).list_documents())
    return qdrant_documents, vector_size, collection_created


def _collection_vector_size(info: object, collection: str, host: str) -> int:
    params = getattr(getattr(info, "config", None), "params", None)
    vectors = getattr(params, "vectors", None)
    if vectors is None:
        raise ExternalServiceError(
            f"Qdrant collection has no vector config (host={host}, collection={collection})."
        )

    size = getattr(vectors, "size", None)
    if size is not None:
        return int(size)

    if isinstance(vectors, dict):
        if len(vectors) != 1:
            raise ExternalServiceError(
                "Qdrant collection uses named vectors; importer expects a single unnamed vector "
                f"(host={host}, collection={collection})."
            )
        only_vector = next(iter(vectors.values()))
        named_size = getattr(only_vector, "size", None)
        if named_size is None:
            raise ExternalServiceError(
                f"Qdrant named vector config is missing size (host={host}, collection={collection})."
            )
        return int(named_size)

    raise ExternalServiceError(
        f"Unable to read Qdrant vector size (host={host}, collection={collection})."
    )


def _qdrant_host(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc:
        return parsed.netloc
    return url
