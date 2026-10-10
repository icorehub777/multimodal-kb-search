import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kbsearch_importer.config import ConfigError
from kbsearch_importer.google_credentials import ensure_google_application_credentials, load_service_account_email


class GoogleCredentialsTests(unittest.TestCase):
    def test_ensure_google_application_credentials_rejects_missing_fixed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("kbsearch_importer.config.DEFAULT_GCP_ADC_FILE", Path(temp_dir) / "missing.json"):
                with self.assertRaisesRegex(ConfigError, "not found"):
                    ensure_google_application_credentials()

    def test_ensure_google_application_credentials_resolves_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adc_path = Path(temp_dir) / "gcp-adc.json"
            adc_path.write_text('{"client_email": "svc@example.com"}', encoding="utf-8")
            with patch("kbsearch_importer.config.DEFAULT_GCP_ADC_FILE", adc_path), patch.dict(
                os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/ignored/key.json"}, clear=True
            ):
                resolved = ensure_google_application_credentials()
                self.assertEqual(resolved, str(adc_path))
                self.assertEqual(os.environ["GOOGLE_APPLICATION_CREDENTIALS"], "/ignored/key.json")

    def test_ensure_google_application_credentials_rejects_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adc_path = Path(temp_dir) / "missing.json"
            with patch("kbsearch_importer.config.DEFAULT_GCP_ADC_FILE", adc_path):
                with self.assertRaisesRegex(ConfigError, "not found"):
                    ensure_google_application_credentials()

    def test_load_service_account_email_reads_client_email_from_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adc_path = Path(temp_dir) / "gcp-adc.json"
            adc_path.write_text(
                json.dumps({"client_email": "svc@example.com"}),
                encoding="utf-8",
            )
            with patch("kbsearch_importer.config.DEFAULT_GCP_ADC_FILE", adc_path):
                email = load_service_account_email()

        self.assertEqual(email, "svc@example.com")

    def test_load_service_account_email_rejects_non_mapping_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adc_path = Path(temp_dir) / "gcp-adc.json"
            adc_path.write_text("[]", encoding="utf-8")
            with patch("kbsearch_importer.config.DEFAULT_GCP_ADC_FILE", adc_path):
                with self.assertRaisesRegex(ConfigError, "JSON object"):
                    load_service_account_email()


if __name__ == "__main__":
    unittest.main()
