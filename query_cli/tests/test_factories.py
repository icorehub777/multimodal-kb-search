import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from kbsearch_cli.config import QueryCliConfig
from kbsearch_cli.factories import (
    _create_drive_service,
    discard_oauth_token_cache,
    load_google_credentials,
)


def _sample_config(root: Path) -> QueryCliConfig:
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    oauth_client = config_dir / "oauth_client.json"
    token_cache = config_dir / "token_cache.json"
    oauth_client.write_text("{}", encoding="utf-8")
    return QueryCliConfig(
        secure_backend_base_url="http://127.0.0.1:8000",
        google_oauth_client_config=oauth_client,
        google_oauth_token_cache=token_cache,
        query_results_root=root / "query_results",
        query_logs_root=root / "logs",
        libreoffice_command=str(root / "soffice.exe"),
        cjk_font_path=root / "msjh.ttc",
    )


class GoogleCredentialsFactoryTests(unittest.TestCase):
    def test_discard_oauth_token_cache_removes_existing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir))
            config.google_oauth_token_cache.write_text("{}", encoding="utf-8")

            removed = discard_oauth_token_cache(config)

            self.assertTrue(removed)
            self.assertFalse(config.google_oauth_token_cache.exists())

    def test_load_google_credentials_discards_cache_when_refresh_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir))
            config.google_oauth_token_cache.write_text("{}", encoding="utf-8")
            credentials = MagicMock()
            credentials.expired = True
            credentials.refresh_token = "refresh"
            credentials.valid = False

            with patch(
                "google.oauth2.credentials.Credentials.from_authorized_user_file",
                return_value=credentials,
            ), patch(
                "google.auth.transport.requests.Request",
            ), patch.object(
                credentials,
                "refresh",
                side_effect=RuntimeError("invalid_grant"),
            ):
                result = load_google_credentials(config)

            self.assertIsNone(result)
            self.assertFalse(config.google_oauth_token_cache.exists())

    def test_load_google_credentials_discards_cache_when_token_invalid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir))
            config.google_oauth_token_cache.write_text("{}", encoding="utf-8")
            credentials = MagicMock()
            credentials.expired = False
            credentials.refresh_token = None
            credentials.valid = False

            with patch(
                "google.oauth2.credentials.Credentials.from_authorized_user_file",
                return_value=credentials,
            ):
                result = load_google_credentials(config)

            self.assertIsNone(result)
            self.assertFalse(config.google_oauth_token_cache.exists())

    def test_create_drive_service_reruns_oauth_when_discarded_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir))
            config.google_oauth_token_cache.write_text("{}", encoding="utf-8")
            new_credentials = MagicMock()
            new_credentials.valid = True
            new_credentials.to_json.return_value = json.dumps({"token": "new"})

            with patch(
                "kbsearch_cli.factories.load_google_credentials",
                side_effect=[None],
            ), patch(
                "google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file",
            ) as from_client_secrets, patch(
                "kbsearch_cli.factories.build_drive_service",
                return_value=object(),
            ) as build_drive_service:
                flow = from_client_secrets.return_value
                flow.run_local_server.return_value = new_credentials

                _create_drive_service(config)

            flow.run_local_server.assert_called_once_with(port=0)
            build_drive_service.assert_called_once_with(new_credentials)
            self.assertTrue(config.google_oauth_token_cache.exists())
            self.assertEqual(
                config.google_oauth_token_cache.read_text(encoding="utf-8"),
                json.dumps({"token": "new"}),
            )


if __name__ == "__main__":
    unittest.main()
