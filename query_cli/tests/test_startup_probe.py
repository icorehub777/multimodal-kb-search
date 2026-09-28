import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from kbsearch_cli.config import ConfigError, QueryCliConfig
from kbsearch_cli.errors import AuthenticationError, ExternalServiceError
from kbsearch_cli.startup_probe import probe_startup_environment


class FakeCredentialStore:
    def __init__(self, value: str | None = "credential") -> None:
        self.value = value
        self.deleted = False

    def read(self) -> str | None:
        return self.value

    def write(self, value: str) -> None:
        self.value = value

    def delete(self) -> bool:
        self.deleted = True
        self.value = None
        return True


def _sample_config(root: Path, *, cjk_font_exists: bool = True) -> QueryCliConfig:
    oauth_client = root / "config" / "oauth_client.json"
    oauth_client.parent.mkdir(parents=True, exist_ok=True)
    cjk_font = root / "msjh.ttc"
    if cjk_font_exists:
        cjk_font.write_bytes(b"")
    return QueryCliConfig(
        secure_backend_base_url="http://127.0.0.1:8000",
        google_oauth_client_config=oauth_client,
        query_logs_root=root / "logs",
        tasks_root=root / "tasks",
        viewer_port=8501,
        query_log_retention_days=14,
        log_level="INFO",
        cjk_font_path=cjk_font,
    )


def _drive_service(error: Exception | None = None):
    request = MagicMock()
    request.execute.side_effect = error
    service = MagicMock()
    service.about.return_value.get.return_value = request
    return service


class StartupProbeTests(unittest.TestCase):
    def test_probe_succeeds_when_services_and_local_tools_are_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir))
            response = type("Response", (), {"status_code": 200})()
            with patch("shutil.which", return_value="soffice"), patch(
                "requests.get", return_value=response
            ) as get, patch(
                "kbsearch_cli.startup_probe.load_google_credentials",
                return_value=object(),
            ):
                result = probe_startup_environment(
                    config,
                    credential_store=FakeCredentialStore(),
                    create_drive_service=lambda _: _drive_service(),
                )
        self.assertTrue(result.google_drive_authenticated)
        self.assertEqual(get.call_args.kwargs["timeout"], (10, 30))

    def test_probe_requires_authentication_without_stored_credentials(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir))
            with patch("shutil.which", return_value="soffice"), patch(
                "kbsearch_cli.startup_probe.load_google_credentials", return_value=None
            ), self.assertRaisesRegex(AuthenticationError, "kbsearch login"):
                probe_startup_environment(
                    config,
                    credential_store=FakeCredentialStore(None),
                    probe_secure_backend=False,
                )

    def test_probe_fails_when_libreoffice_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir))
            with patch("shutil.which", return_value=None), self.assertRaisesRegex(
                ConfigError, "LibreOffice command not found"
            ):
                probe_startup_environment(config, probe_secure_backend=False)

    def test_probe_fails_when_cjk_font_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir), cjk_font_exists=False)
            with patch("shutil.which", return_value="soffice"), self.assertRaisesRegex(
                ConfigError, "CJK font not found"
            ):
                probe_startup_environment(config, probe_secure_backend=False)

    def test_probe_fails_when_secure_backend_unreachable(self):
        import requests

        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir))
            with patch("shutil.which", return_value="soffice"), patch(
                "requests.get", side_effect=requests.RequestException("connection refused")
            ), self.assertRaisesRegex(ExternalServiceError, "Secure backend unreachable"):
                probe_startup_environment(config)

    def test_probe_preserves_credential_on_transient_drive_failure(self):
        store = FakeCredentialStore()
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir))
            with patch("shutil.which", return_value="soffice"), patch(
                "kbsearch_cli.startup_probe.load_google_credentials", return_value=object()
            ), self.assertRaisesRegex(ExternalServiceError, "validation failed"):
                probe_startup_environment(
                    config,
                    credential_store=store,
                    create_drive_service=lambda _: _drive_service(RuntimeError("timeout")),
                    probe_secure_backend=False,
                )
        self.assertFalse(store.deleted)

    def test_probe_deletes_explicitly_invalid_credential(self):
        store = FakeCredentialStore()
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir))
            with patch("shutil.which", return_value="soffice"), patch(
                "kbsearch_cli.startup_probe.load_google_credentials", return_value=object()
            ), self.assertRaisesRegex(AuthenticationError, "kbsearch login"):
                probe_startup_environment(
                    config,
                    credential_store=store,
                    create_drive_service=lambda _: _drive_service(RuntimeError("invalid_token")),
                    probe_secure_backend=False,
                )
        self.assertTrue(store.deleted)


if __name__ == "__main__":
    unittest.main()
