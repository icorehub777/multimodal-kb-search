import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kbsearch_cli.config import ConfigError, find_query_cli_env_file, load_query_cli_config


class QueryCliConfigTests(unittest.TestCase):
    def test_load_query_cli_config_reads_required_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            internal_root = Path(temp_dir) / "agent_runtime" / "_internal"
            config_dir = internal_root / "config"
            config_dir.mkdir(parents=True)
            env_file = config_dir / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=config/oauth_client.json",
                        "GOOGLE_OAUTH_TOKEN_CACHE=config/token_cache.json",
                        "KBSEARCH_QUERY_LOGS_ROOT=logs",
                        "KBSEARCH_CJK_FONT_PATH=C:/Windows/Fonts/msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True), patch(
                "pathlib.Path.cwd", return_value=internal_root
            ):
                config = load_query_cli_config(env_file)

        self.assertEqual(config.secure_backend_base_url, "http://127.0.0.1:8000")
        self.assertEqual(
            config.google_oauth_client_config,
            internal_root / "config" / "oauth_client.json",
        )
        self.assertEqual(
            config.google_oauth_token_cache,
            internal_root / "config" / "token_cache.json",
        )
        self.assertEqual(config.query_logs_root, internal_root / "logs")
        self.assertEqual(config.cjk_font_path, Path("C:/Windows/Fonts/msjh.ttc"))
        self.assertTrue(config.render_downloaded_files)

    def test_load_query_cli_config_allows_missing_render_tools_when_rendering_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                        "GOOGLE_OAUTH_TOKEN_CACHE=token.json",
                        "KBSEARCH_RENDER_DOWNLOADED_FILES=false",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_query_cli_config(env_file)

        self.assertFalse(config.render_downloaded_files)
        self.assertIsNone(config.cjk_font_path)

    def test_load_query_cli_config_rejects_invalid_render_downloaded_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                        "GOOGLE_OAUTH_TOKEN_CACHE=token.json",
                        "KBSEARCH_RENDER_DOWNLOADED_FILES=maybe",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "KBSEARCH_RENDER_DOWNLOADED_FILES"):
                    load_query_cli_config(env_file)

    def test_load_query_cli_config_defaults_runtime_paths_to_cwd(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                        "GOOGLE_OAUTH_TOKEN_CACHE=token.json",
                        "KBSEARCH_CJK_FONT_PATH=C:/Windows/Fonts/msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )
            cwd = Path(temp_dir) / "query_cli"
            cwd.mkdir()

            with patch.dict(os.environ, {}, clear=True), patch("pathlib.Path.cwd", return_value=cwd):
                config = load_query_cli_config(env_file)

        self.assertEqual(config.query_logs_root, cwd / "logs")

    def test_find_query_cli_env_file_uses_current_working_directory_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir) / "agent_runtime" / "_internal"
            env_file = cwd / "config" / ".env"
            env_file.parent.mkdir(parents=True)
            env_file.write_text("", encoding="utf-8")

            with patch("pathlib.Path.cwd", return_value=cwd):
                self.assertEqual(find_query_cli_env_file(), env_file)

    def test_load_query_cli_config_rejects_missing_backend_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                        "GOOGLE_OAUTH_TOKEN_CACHE=token.json",
                        "KBSEARCH_CJK_FONT_PATH=C:/Windows/Fonts/msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "KBSEARCH_SECURE_BACKEND_BASE_URL"):
                    load_query_cli_config(env_file)

    def test_load_query_cli_config_rejects_missing_cjk_font_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                        "GOOGLE_OAUTH_TOKEN_CACHE=token.json",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "KBSEARCH_CJK_FONT_PATH"):
                    load_query_cli_config(env_file)

    def test_load_query_cli_config_rejects_relative_cjk_font_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                        "GOOGLE_OAUTH_TOKEN_CACHE=token.json",
                        "KBSEARCH_CJK_FONT_PATH=msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "absolute path"):
                    load_query_cli_config(env_file)


if __name__ == "__main__":
    unittest.main()
