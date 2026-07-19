import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import APP_ROOT, DEFAULT_LOG_FILE, ConfigError, load_backend_config


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
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=4",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_backend_config(env_file)

        self.assertEqual(config.dashscope_embedding_model, "qwen-vl")
        self.assertEqual(config.qdrant_collection, "kbsearch")
        self.assertEqual(config.qdrant_vector_size, 4)
        self.assertEqual(config.dashscope_image_max_bytes, 9_728_000)
        self.assertEqual(config.dashscope_jpeg_quality, 95)
        self.assertEqual(config.log_file_path, DEFAULT_LOG_FILE)

    def test_load_backend_config_reads_dashscope_image_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "DASHSCOPE_VECTOR_SIZE=4",
                        "DASHSCOPE_IMAGE_MAX_BYTES=9000000",
                        "DASHSCOPE_JPEG_QUALITY=90",
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=4",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_backend_config(env_file)

        self.assertEqual(config.dashscope_image_max_bytes, 9_000_000)
        self.assertEqual(config.dashscope_jpeg_quality, 90)

    def test_load_backend_config_rejects_invalid_dashscope_image_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "DASHSCOPE_VECTOR_SIZE=4",
                        "DASHSCOPE_IMAGE_MAX_BYTES=10485761",
                        "DASHSCOPE_JPEG_QUALITY=101",
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=4",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "DASHSCOPE_IMAGE_MAX_BYTES"):
                    load_backend_config(env_file)

    def test_load_backend_config_rejects_invalid_dashscope_jpeg_quality(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "DASHSCOPE_VECTOR_SIZE=4",
                        "DASHSCOPE_JPEG_QUALITY=101",
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=4",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "DASHSCOPE_JPEG_QUALITY"):
                    load_backend_config(env_file)

    def test_load_backend_config_uses_fixed_log_file_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "DASHSCOPE_VECTOR_SIZE=4",
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=4",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_backend_config(env_file)

        self.assertEqual(config.log_file_path, APP_ROOT / "logs" / "secure_backend.log")

    def test_load_backend_config_allows_empty_qdrant_api_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "DASHSCOPE_VECTOR_SIZE=4",
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=4",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_backend_config(env_file)

        self.assertIsNone(config.qdrant_api_key)

    def test_load_backend_config_rejects_missing_required_value(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "DASHSCOPE_VECTOR_SIZE=4",
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=4",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "DASHSCOPE_API_KEY"):
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
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=3",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "must match"):
                    load_backend_config(env_file)


if __name__ == "__main__":
    unittest.main()
