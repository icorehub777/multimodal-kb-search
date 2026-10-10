import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kbsearch_backend.config import APP_ROOT, DEFAULT_LOG_FILE, ConfigError, load_backend_config


class BackendConfigTests(unittest.TestCase):
    def test_load_backend_config_uses_one_vector_dimension(self):
        values = {
            "SECURE_BACKEND_API_KEY": "backend-secret",
            "DASHSCOPE_API_KEY": "secret",
            "DASHSCOPE_EMBEDDING_MODEL": "qwen-vl",
            "KBSEARCH_VECTOR_SIZE": "4",
            "QDRANT_URL": "http://qdrant:6333",
            "QDRANT_COLLECTION": "kbsearch",
        }
        with patch.dict(os.environ, values, clear=True):
            config = load_backend_config(None)
        self.assertEqual(config.vector_size, 4)

    def test_runtime_root_is_independent_of_package_installation(self):
        self.assertEqual(APP_ROOT, Path("/app"))

    def test_load_backend_config_reads_required_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "SECURE_BACKEND_API_KEY=backend-secret",
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "KBSEARCH_VECTOR_SIZE=4",
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_backend_config(env_file)

        self.assertEqual(config.dashscope_embedding_model, "qwen-vl")
        self.assertEqual(config.secure_backend_api_key, "backend-secret")
        self.assertEqual(config.qdrant_collection, "kbsearch")
        self.assertEqual(config.vector_size, 4)
        self.assertEqual(config.dashscope_image_max_bytes, 9_728_000)
        self.assertEqual(config.dashscope_jpeg_quality, 95)
        self.assertEqual(config.log_file_path, DEFAULT_LOG_FILE)
        self.assertEqual(config.max_query_length, 4_000)
        self.assertEqual(config.max_images, 5)
        self.assertEqual(config.max_search_limit, 100)
        self.assertEqual(config.log_level, "INFO")

    def test_load_backend_config_reads_dashscope_image_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "SECURE_BACKEND_API_KEY=backend-secret",
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "KBSEARCH_VECTOR_SIZE=4",
                        "DASHSCOPE_IMAGE_MAX_BYTES=9000000",
                        "DASHSCOPE_JPEG_QUALITY=90",
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
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
                        "SECURE_BACKEND_API_KEY=backend-secret",
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "KBSEARCH_VECTOR_SIZE=4",
                        "DASHSCOPE_IMAGE_MAX_BYTES=10485761",
                        "DASHSCOPE_JPEG_QUALITY=101",
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
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
                        "SECURE_BACKEND_API_KEY=backend-secret",
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "KBSEARCH_VECTOR_SIZE=4",
                        "DASHSCOPE_JPEG_QUALITY=101",
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
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
                        "SECURE_BACKEND_API_KEY=backend-secret",
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "KBSEARCH_VECTOR_SIZE=4",
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
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
                        "SECURE_BACKEND_API_KEY=backend-secret",
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "KBSEARCH_VECTOR_SIZE=4",
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
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
                        "SECURE_BACKEND_API_KEY=backend-secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "KBSEARCH_VECTOR_SIZE=4",
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "DASHSCOPE_API_KEY"):
                    load_backend_config(env_file)

    def test_load_backend_config_requires_secure_backend_api_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "KBSEARCH_VECTOR_SIZE=4",
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "SECURE_BACKEND_API_KEY"):
                    load_backend_config(env_file)

    def test_load_backend_config_requires_vector_size(self):
        values = {
            "SECURE_BACKEND_API_KEY": "backend-secret",
            "DASHSCOPE_API_KEY": "secret",
            "DASHSCOPE_EMBEDDING_MODEL": "qwen-vl",
            "QDRANT_URL": "http://qdrant:6333",
            "QDRANT_COLLECTION": "kbsearch",
        }
        with patch.dict(os.environ, values, clear=True):
            with self.assertRaisesRegex(ConfigError, "KBSEARCH_VECTOR_SIZE"):
                load_backend_config(None)

    def test_load_backend_config_rejects_non_positive_vector_sizes(self):
        for name, value in (("KBSEARCH_VECTOR_SIZE", "0"), ("KBSEARCH_VECTOR_SIZE", "-1")):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_dir:
                values = {
                    "SECURE_BACKEND_API_KEY": "backend-secret",
                    "DASHSCOPE_API_KEY": "secret",
                    "DASHSCOPE_EMBEDDING_MODEL": "qwen-vl",
                    "KBSEARCH_VECTOR_SIZE": "4",
                    "QDRANT_URL": "http://127.0.0.1:6333",
                    "QDRANT_API_KEY": "",
                    "QDRANT_COLLECTION": "kbsearch",
                }
                values[name] = value
                env_file = Path(temp_dir) / ".env"
                env_file.write_text(
                    "\n".join(f"{key}={item}" for key, item in values.items()),
                    encoding="utf-8",
                )

                with patch.dict(os.environ, {}, clear=True):
                    with self.assertRaisesRegex(ConfigError, name):
                        load_backend_config(env_file)

    def test_load_backend_config_reads_request_limits_and_log_level(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "SECURE_BACKEND_API_KEY=backend-secret",
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen-vl",
                        "KBSEARCH_VECTOR_SIZE=4",
                        "QDRANT_URL=http://127.0.0.1:6333",
                        "QDRANT_API_KEY=",
                        "QDRANT_COLLECTION=kbsearch",
                        "SECURE_BACKEND_MAX_QUERY_LENGTH=20",
                        "SECURE_BACKEND_MAX_IMAGES=2",
                        "SECURE_BACKEND_MAX_SEARCH_LIMIT=7",
                        "SECURE_BACKEND_LOG_LEVEL=debug",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_backend_config(env_file)

        self.assertEqual(config.max_query_length, 20)
        self.assertEqual(config.max_images, 2)
        self.assertEqual(config.max_search_limit, 7)
        self.assertEqual(config.log_level, "DEBUG")

    def test_load_backend_config_rejects_invalid_request_limit_and_log_level(self):
        for name, value in (
            ("SECURE_BACKEND_MAX_QUERY_LENGTH", "0"),
            ("SECURE_BACKEND_MAX_IMAGES", "0"),
            ("SECURE_BACKEND_MAX_SEARCH_LIMIT", "-1"),
            ("SECURE_BACKEND_LOG_LEVEL", "TRACE"),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_dir:
                values = {
                    "SECURE_BACKEND_API_KEY": "backend-secret",
                    "DASHSCOPE_API_KEY": "secret",
                    "DASHSCOPE_EMBEDDING_MODEL": "qwen-vl",
                    "KBSEARCH_VECTOR_SIZE": "4",
                    "QDRANT_URL": "http://127.0.0.1:6333",
                    "QDRANT_API_KEY": "",
                    "QDRANT_COLLECTION": "kbsearch",
                    name: value,
                }
                env_file = Path(temp_dir) / ".env"
                env_file.write_text(
                    "\n".join(f"{key}={item}" for key, item in values.items()),
                    encoding="utf-8",
                )

                with patch.dict(os.environ, {}, clear=True):
                    with self.assertRaisesRegex(ConfigError, name):
                        load_backend_config(env_file)


if __name__ == "__main__":
    unittest.main()
