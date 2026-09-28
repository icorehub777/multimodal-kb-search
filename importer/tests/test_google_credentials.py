import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import ConfigError
from app.google_credentials import ensure_google_application_credentials, load_service_account_email


class GoogleCredentialsTests(unittest.TestCase):
    def test_ensure_google_application_credentials_rejects_missing_env(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ConfigError, "GOOGLE_APPLICATION_CREDENTIALS"):
                ensure_google_application_credentials()

    def test_ensure_google_application_credentials_resolves_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adc_path = Path(temp_dir) / "gcp-adc.json"
            adc_path.write_text('{"client_email": "svc@example.com"}', encoding="utf-8")
            with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": str(adc_path)}, clear=True):
                resolved = ensure_google_application_credentials()
                self.assertEqual(resolved, str(adc_path))
                self.assertEqual(os.environ["GOOGLE_APPLICATION_CREDENTIALS"], str(adc_path))

    def test_ensure_google_application_credentials_rejects_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adc_path = Path(temp_dir) / "missing.json"
            with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": str(adc_path)}, clear=True):
                with self.assertRaisesRegex(ConfigError, "not found"):
                    ensure_google_application_credentials()

    def test_load_service_account_email_reads_client_email_from_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adc_path = Path(temp_dir) / "gcp-adc.json"
            adc_path.write_text(
                json.dumps({"client_email": "svc@example.com"}),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": str(adc_path)}, clear=True):
                email = load_service_account_email()

        self.assertEqual(email, "svc@example.com")

    def test_load_service_account_email_rejects_non_mapping_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adc_path = Path(temp_dir) / "gcp-adc.json"
            adc_path.write_text("[]", encoding="utf-8")
            with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": str(adc_path)}, clear=True):
                with self.assertRaisesRegex(ConfigError, "JSON object"):
                    load_service_account_email()


if __name__ == "__main__":
    unittest.main()
