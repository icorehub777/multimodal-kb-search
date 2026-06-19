import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kbsearch_cli.config import ConfigError, QueryCliConfig
from kbsearch_cli.errors import ExternalServiceError
from kbsearch_cli.startup_probe import probe_startup_environment


def _sample_config(
    root: Path,
    *,
    oauth_client_exists: bool = True,
    token_cache_exists: bool = False,
    cjk_font_exists: bool = True,
) -> QueryCliConfig:
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    oauth_client = config_dir / "oauth_client.json"
    token_cache = config_dir / "token_cache.json"
    cjk_font = root / "msjh.ttc"

    if oauth_client_exists:
        oauth_client.write_text("{}", encoding="utf-8")
    if token_cache_exists:
        token_cache.write_text("{}", encoding="utf-8")
    if cjk_font_exists:
        cjk_font.write_bytes(b"")

    return QueryCliConfig(
        secure_backend_base_url="http://127.0.0.1:8000",
        google_oauth_client_config=oauth_client,
        google_oauth_token_cache=token_cache,
        query_logs_root=root / "logs",
        cjk_font_path=cjk_font,
    )


class StartupProbeTests(unittest.TestCase):
    def test_probe_succeeds_when_local_tools_and_backend_are_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir))
            fake_response = type("FakeResponse", (), {"status_code": 200})()

            with patch("shutil.which", return_value="soffice"), patch(
                "requests.get", return_value=fake_response
            ):
                result = probe_startup_environment(config)

        self.assertFalse(result.google_drive_authenticated)
        self.assertEqual(result.secure_backend_base_url, "http://127.0.0.1:8000")

    def test_probe_fails_when_oauth_client_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir), oauth_client_exists=False)

            with self.assertRaisesRegex(ConfigError, "Google OAuth client not found"):
                probe_startup_environment(config)

    def test_probe_fails_when_libreoffice_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir))

            with patch("shutil.which", return_value=None), self.assertRaisesRegex(
                ConfigError,
                "LibreOffice command not found in PATH",
            ):
                probe_startup_environment(config)

    def test_probe_fails_when_cjk_font_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir), cjk_font_exists=False)

            with patch("shutil.which", return_value="soffice"), self.assertRaisesRegex(
                ConfigError,
                "CJK font not found",
            ):
                probe_startup_environment(config)

    def test_probe_fails_when_secure_backend_unreachable(self):
        import requests

        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir))

            with patch("shutil.which", return_value="soffice"), patch(
                "requests.get",
                side_effect=requests.RequestException("connection refused"),
            ):
                with self.assertRaisesRegex(
                    ExternalServiceError,
                    "Secure backend unreachable",
                ):
                    probe_startup_environment(config)

    def test_probe_validates_google_drive_when_token_cache_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _sample_config(Path(temp_dir), token_cache_exists=True)
            fake_response = type("FakeResponse", (), {"status_code": 200})()
            fake_drive_service = type(
                "FakeDriveService",
                (),
                {
                    "about": lambda self: type(
                        "AboutResource",
                        (),
                        {
                            "get": lambda self, fields: type(
                                "AboutRequest",
                                (),
                                {"execute": lambda self: {"user": {"emailAddress": "user@example.com"}}},
                            )()
                        },
                    )()
                },
            )()

            with patch("shutil.which", return_value="soffice"), patch(
                "requests.get", return_value=fake_response
            ), patch(
                "kbsearch_cli.startup_probe.load_google_credentials",
                return_value=type("Credentials", (), {"valid": True})(),
            ), patch(
                "kbsearch_cli.factories.build_drive_service",
                return_value=fake_drive_service,
            ):
                result = probe_startup_environment(config)

        self.assertTrue(result.google_drive_authenticated)


if __name__ == "__main__":
    unittest.main()
