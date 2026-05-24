import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kbsearch_cli.config import ConfigError, load_query_cli_config


class QueryCliConfigTests(unittest.TestCase):
    def test_load_query_cli_config_reads_required_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "query_cli"
            config_dir = root / "config"
            config_dir.mkdir(parents=True)
            env_file = config_dir / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                        "GOOGLE_OAUTH_TOKEN_CACHE=C:/Users/Marco/.kbsearch/token.json",
                        "KBSEARCH_QUERY_RESULTS_ROOT=../agent_runtime/query_results",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_query_cli_config(env_file)

        self.assertEqual(config.secure_backend_base_url, "http://127.0.0.1:8000")
        self.assertEqual(config.google_oauth_client_config, root / "client.json")
        self.assertEqual(config.google_oauth_token_cache, Path("C:/Users/Marco/.kbsearch/token.json"))
        self.assertEqual(config.query_results_root, root / "../agent_runtime/query_results")

    def test_load_query_cli_config_rejects_missing_backend_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                        "GOOGLE_OAUTH_TOKEN_CACHE=token.json",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "KBSEARCH_SECURE_BACKEND_BASE_URL"):
                    load_query_cli_config(env_file)


if __name__ == "__main__":
    unittest.main()
