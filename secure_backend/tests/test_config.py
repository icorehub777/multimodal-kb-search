import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kbsearch_secure_backend.config import APP_ROOT, ConfigError, load_backend_config


class BackendConfigTests(unittest.TestCase):
    def test_load_backend_config_reads_required_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "DASHSCOPE_VECTOR_SIZE=4",
                        "QDRANT_URL=https://qdrant.example.com",
                        "QDRANT_API_KEY=qdrant-secret",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=4",
                        "KBSEARCH_SECURE_BACKEND_LOG_FILE=logs/backend.log",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_backend_config(env_file)

        self.assertEqual(config.dashscope_embedding_model, "qwen-vl")
        self.assertEqual(config.qdrant_collection, "kbsearch")
        self.assertEqual(config.qdrant_vector_size, 4)
        self.assertEqual(config.log_file_path, APP_ROOT / "logs" / "backend.log")

    def test_load_backend_config_resolves_relative_log_path_from_app_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir) / "etc" / "config"
            env_dir.mkdir(parents=True)
            env_file = env_dir / "kbsearch.env"
            env_file.write_text(
                "\n".join(
                    [
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "DASHSCOPE_VECTOR_SIZE=4",
                        "QDRANT_URL=https://qdrant.example.com",
                        "QDRANT_API_KEY=qdrant-secret",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=4",
                        "KBSEARCH_SECURE_BACKEND_LOG_FILE=logs/backend.log",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_backend_config(env_file)

        self.assertEqual(config.log_file_path, APP_ROOT / "logs" / "backend.log")

    def test_load_backend_config_rejects_missing_required_value(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "DASHSCOPE_VECTOR_SIZE=4",
                        "QDRANT_URL=https://qdrant.example.com",
                        "QDRANT_API_KEY=qdrant-secret",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=4",
                        "KBSEARCH_SECURE_BACKEND_LOG_FILE=logs/backend.log",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "DASHSCOPE_API_KEY"):
                    load_backend_config(env_file)

    def test_load_backend_config_rejects_missing_log_file_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "DASHSCOPE_VECTOR_SIZE=4",
                        "QDRANT_URL=https://qdrant.example.com",
                        "QDRANT_API_KEY=qdrant-secret",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=4",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "KBSEARCH_SECURE_BACKEND_LOG_FILE"):
                    load_backend_config(env_file)

    def test_load_backend_config_rejects_vector_size_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "DASHSCOPE_VECTOR_SIZE=4",
                        "QDRANT_URL=https://qdrant.example.com",
                        "QDRANT_API_KEY=qdrant-secret",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=3",
                        "KBSEARCH_SECURE_BACKEND_LOG_FILE=logs/backend.log",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "must match"):
                    load_backend_config(env_file)


if __name__ == "__main__":
    unittest.main()
