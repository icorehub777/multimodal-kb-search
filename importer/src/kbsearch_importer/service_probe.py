from __future__ import annotations

import base64
from pathlib import Path
from tempfile import TemporaryDirectory

from kbsearch_importer.config import ImporterConfig
from kbsearch_importer.dashscope_embedder import DashScopeImageEmbeddingClient
from kbsearch_importer.factories import create_drive_scanner, create_qdrant_index

TINY_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def probe_external_services(config: ImporterConfig) -> dict[str, int]:
    documents = create_drive_scanner(config).list_documents()
    qdrant_documents = create_qdrant_index(config).list_documents()

    client = DashScopeImageEmbeddingClient(
        api_key=config.dashscope_api_key,
        model=config.dashscope_embedding_model,
        dimension=config.dashscope_vector_size,
    )
    with TemporaryDirectory() as temp_dir:
        image_path = Path(temp_dir) / "sample.png"
        image_path.write_bytes(base64.b64decode(TINY_PNG_BASE64))
        vector = client.embed_image(image_path)

    return {
        "google_documents": len(documents),
        "dashscope_dimension": len(vector),
        "qdrant_documents": len(qdrant_documents),
    }
