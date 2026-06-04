import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.config import BackendConfig
from app.errors import ExternalServiceError
from app.startup_probe import probe_startup_environment


def _backend_config() -> BackendConfig:
    return BackendConfig(
        dashscope_api_key="dashscope-key",
        dashscope_embedding_model="qwen3-vl-embedding",
        dashscope_vector_size=4,
        qdrant_url="https://qdrant.example.com",
        qdrant_api_key="qdrant-key",
        qdrant_collection="kbsearch",
        qdrant_vector_size=4,
        log_file_path=__import__("pathlib").Path("logs/secure_backend.log"),
    )


class StartupProbeTests(unittest.TestCase):
    def test_probe_startup_environment_succeeds(self):
        config = _backend_config()
        collection_info = SimpleNamespace(
            points_count=12,
            config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=4))),
        )
        with patch(
            "app.startup_probe.DashScopeQueryEmbeddingClient.embed_query",
            return_value=[0.1, 0.2, 0.3, 0.4],
        ), patch("qdrant_client.QdrantClient") as qdrant_client_cls:
            qdrant_client = qdrant_client_cls.return_value
            qdrant_client.collection_exists.return_value = True
            qdrant_client.get_collection.return_value = collection_info

            result = probe_startup_environment(config)

        self.assertEqual(result.dashscope_dimension, 4)
        self.assertEqual(result.qdrant_points_count, 12)
        self.assertEqual(result.qdrant_collection, "kbsearch")
        self.assertEqual(result.qdrant_host, "qdrant.example.com")

    def test_probe_startup_environment_fails_when_collection_missing(self):
        config = _backend_config()
        with patch(
            "app.startup_probe.DashScopeQueryEmbeddingClient.embed_query",
            return_value=[0.1, 0.2, 0.3, 0.4],
        ), patch("qdrant_client.QdrantClient") as qdrant_client_cls:
            qdrant_client = qdrant_client_cls.return_value
            qdrant_client.collection_exists.return_value = False

            with self.assertRaises(ExternalServiceError) as ctx:
                probe_startup_environment(config)

        self.assertIn("does not exist", str(ctx.exception))
        self.assertIn("kbsearch", str(ctx.exception))

    def test_probe_startup_environment_fails_when_vector_size_mismatch(self):
        config = _backend_config()
        collection_info = SimpleNamespace(
            points_count=1,
            config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=8))),
        )
        with patch(
            "app.startup_probe.DashScopeQueryEmbeddingClient.embed_query",
            return_value=[0.1, 0.2, 0.3, 0.4],
        ), patch("qdrant_client.QdrantClient") as qdrant_client_cls:
            qdrant_client = qdrant_client_cls.return_value
            qdrant_client.collection_exists.return_value = True
            qdrant_client.get_collection.return_value = collection_info

            with self.assertRaises(ExternalServiceError) as ctx:
                probe_startup_environment(config)

        self.assertIn("vector size mismatch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
