import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from kbsearch_cli.config import LoginConfig, QueryCliConfig
from kbsearch_cli.errors import AuthenticationError, ExternalServiceError
from kbsearch_cli.factories import (
    create_drive_service,
    create_query_orchestrator,
    load_google_credentials,
    login_google_drive,
)


class FakeCredentialStore:
    def __init__(self, value: str | None = None) -> None:
        self.value = value
        self.deleted = False

    def read(self) -> str | None:
        return self.value

    def write(self, value: str) -> None:
        self.value = value

    def delete(self) -> bool:
        existed = self.value is not None
        self.value = None
        self.deleted = True
        return existed


def _sample_config(root: Path) -> QueryCliConfig:
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    oauth_client = config_dir / "oauth_client.json"
    oauth_client.write_text("{}", encoding="utf-8")
    return QueryCliConfig(
        secure_backend_base_url="http://127.0.0.1:8000",
        secure_backend_api_key="backend-secret",
        query_logs_root=root / "logs",
        tasks_root=root / "tasks",
        query_log_retention_days=14,
        log_level="INFO",
        cjk_font_path=root / "msjh.ttc",
    )


class GoogleCredentialsFactoryTests(unittest.TestCase):
    def test_create_query_orchestrator_configures_document_processor(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir).resolve())

            with patch("kbsearch_cli.factories.create_drive_service", return_value=object()):
                orchestrator = create_query_orchestrator(config)

        self.assertEqual(orchestrator._document_processor._cjk_font_path, config.cjk_font_path)
        self.assertEqual(orchestrator._backend._api_key, "backend-secret")

    def test_load_google_credentials_deletes_explicitly_revoked_token(self):
        store = FakeCredentialStore(json.dumps({"token": "old"}))
        credentials = MagicMock()
        credentials.expired = True
        credentials.refresh_token = "refresh"
        credentials.valid = False

        with patch(
            "google.oauth2.credentials.Credentials.from_authorized_user_info",
            return_value=credentials,
        ), patch("google.auth.transport.requests.Request"), patch.object(
            credentials,
            "refresh",
            side_effect=RuntimeError("invalid_grant: token revoked"),
        ):
            result = load_google_credentials(store)

        self.assertIsNone(result)
        self.assertTrue(store.deleted)
        self.assertIsNone(store.value)

    def test_load_google_credentials_preserves_token_on_transient_refresh_failure(self):
        original = json.dumps({"token": "old"})
        store = FakeCredentialStore(original)
        credentials = MagicMock()
        credentials.expired = True
        credentials.refresh_token = "refresh"
        credentials.valid = False

        with patch(
            "google.oauth2.credentials.Credentials.from_authorized_user_info",
            return_value=credentials,
        ), patch("google.auth.transport.requests.Request"), patch.object(
            credentials,
            "refresh",
            side_effect=RuntimeError("temporary DNS failure"),
        ):
            with self.assertRaisesRegex(ExternalServiceError, "refresh failed"):
                load_google_credentials(store)

        self.assertFalse(store.deleted)
        self.assertEqual(store.value, original)

    def test_load_google_credentials_deletes_token_on_explicit_401(self):
        store = FakeCredentialStore(json.dumps({"token": "old"}))
        credentials = MagicMock(expired=True, refresh_token="refresh", valid=False)
        error = RuntimeError("unauthorized")
        error.resp = type("Response", (), {"status": 401})()

        with patch(
            "google.oauth2.credentials.Credentials.from_authorized_user_info",
            return_value=credentials,
        ), patch("google.auth.transport.requests.Request"), patch.object(
            credentials, "refresh", side_effect=error
        ):
            self.assertIsNone(load_google_credentials(store))

        self.assertTrue(store.deleted)

    def test_create_drive_service_requires_login_without_opening_browser(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir).resolve())

            with self.assertRaisesRegex(AuthenticationError, "kbsearch login"), patch(
                "google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file"
            ) as oauth_flow:
                create_drive_service(config, credential_store=FakeCredentialStore())

        oauth_flow.assert_not_called()

    def test_login_google_drive_runs_browser_flow_and_writes_credential_store(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            oauth_client = Path(temp_dir).resolve() / "oauth_client.json"
            oauth_client.write_text("{}", encoding="utf-8")
            config = LoginConfig(google_oauth_client_config=oauth_client)
            store = FakeCredentialStore()
            credentials = MagicMock()
            credentials.valid = True
            credentials.to_json.return_value = json.dumps({"token": "new"})

            with patch(
                "google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file",
            ) as from_client_secrets:
                flow = from_client_secrets.return_value
                flow.run_local_server.return_value = credentials

                result = login_google_drive(config, credential_store=store)

        self.assertIs(result, credentials)
        flow.run_local_server.assert_called_once_with(port=0)
        self.assertEqual(store.value, json.dumps({"token": "new"}))


if __name__ == "__main__":
    unittest.main()
