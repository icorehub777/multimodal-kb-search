import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.config import ConfigError, ImporterConfig
from app.errors import ExternalServiceError
from app.startup_probe import probe_startup_environment


def _importer_config(temp_dir: Path) -> ImporterConfig:
    libreoffice = temp_dir / "soffice.exe"
    libreoffice.write_bytes(b"")
    font_path = temp_dir / "font.ttc"
    font_path.write_bytes(b"font")
    source_config = temp_dir / "google_drive_sources.yaml"
    source_config.write_text(
        "\n".join(
            [
                "sources:",
                "  - name: belltaih-shared-drive",
                "    type: shared_drive",
                "    drive_id: drive-1",
            ]
        ),
        encoding="utf-8",
    )
    return ImporterConfig(
        app_root=temp_dir,
        google_drive_source_config=source_config,
        google_drive_sources=(),
        google_dwd_subject_email="user@example.com",
        dashscope_api_key="dashscope-key",
        dashscope_embedding_model="qwen3-vl-embedding",
        dashscope_vector_size=4,
        qdrant_url="https://qdrant.example.com",
        qdrant_api_key="qdrant-key",
        qdrant_collection="kbsearch",
        qdrant_vector_size=4,
        libreoffice_command=str(libreoffice),
        cjk_font_path=font_path,
        keep_success_work_files=True,
        keep_failed_work_files=True,
        log_retention_days=14,
    )


class StartupProbeTests(unittest.TestCase):
    def test_probe_startup_environment_succeeds(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _importer_config(Path(temp_dir))
            collection_info = SimpleNamespace(
                points_count=12,
                config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=4))),
            )
            with patch(
                "app.startup_probe.create_drive_scanner",
            ) as create_scanner, patch(
                "app.startup_probe.DashScopeImageEmbeddingClient.embed_image",
                return_value=[0.1, 0.2, 0.3, 0.4],
            ), patch("app.startup_probe.create_qdrant_index") as create_index, patch(
                "qdrant_client.QdrantClient"
            ) as qdrant_client_cls:
                create_scanner.return_value.list_documents.return_value = [object(), object()]
                create_index.return_value.list_documents.return_value = [object()]
                qdrant_client = qdrant_client_cls.return_value
                qdrant_client.collection_exists.return_value = True
                qdrant_client.get_collection.return_value = collection_info

                result = probe_startup_environment(config)

        self.assertEqual(result.google_documents, 2)
        self.assertEqual(result.dashscope_dimension, 4)
        self.assertEqual(result.qdrant_documents, 1)
        self.assertEqual(result.qdrant_collection, "kbsearch")
        self.assertEqual(result.qdrant_host, "qdrant.example.com")

    def test_probe_startup_environment_fails_when_libreoffice_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _importer_config(Path(temp_dir))
            Path(config.libreoffice_command).unlink()

            with self.assertRaisesRegex(ConfigError, "LibreOffice command not found"):
                probe_startup_environment(config)

    def test_probe_startup_environment_creates_collection_when_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _importer_config(Path(temp_dir))
            collection_info = SimpleNamespace(
                points_count=0,
                config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=4))),
            )
            with patch(
                "app.startup_probe.create_drive_scanner",
            ) as create_scanner, patch(
                "app.startup_probe.DashScopeImageEmbeddingClient.embed_image",
                return_value=[0.1, 0.2, 0.3, 0.4],
            ), patch("app.startup_probe.create_qdrant_index") as create_index, patch(
                "app.startup_probe.ensure_qdrant_collection",
                return_value=True,
            ) as ensure_collection, patch("qdrant_client.QdrantClient") as qdrant_client_cls:
                create_scanner.return_value.list_documents.return_value = []
                create_index.return_value.list_documents.return_value = []
                qdrant_client = qdrant_client_cls.return_value
                qdrant_client.collection_exists.return_value = False
                qdrant_client.get_collection.return_value = collection_info

                result = probe_startup_environment(config)

        ensure_collection.assert_called_once_with(qdrant_client, "kbsearch", 4)
        self.assertTrue(result.qdrant_collection_created)

    def test_probe_startup_environment_fails_when_vector_size_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _importer_config(Path(temp_dir))
            collection_info = SimpleNamespace(
                points_count=1,
                config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=8))),
            )
            with patch(
                "app.startup_probe.create_drive_scanner",
            ) as create_scanner, patch(
                "app.startup_probe.DashScopeImageEmbeddingClient.embed_image",
                return_value=[0.1, 0.2, 0.3, 0.4],
            ), patch("qdrant_client.QdrantClient") as qdrant_client_cls:
                create_scanner.return_value.list_documents.return_value = []
                qdrant_client = qdrant_client_cls.return_value
                qdrant_client.collection_exists.return_value = True
                qdrant_client.get_collection.return_value = collection_info

                with self.assertRaisesRegex(ExternalServiceError, "vector size mismatch"):
                    probe_startup_environment(config)


if __name__ == "__main__":
    unittest.main()
