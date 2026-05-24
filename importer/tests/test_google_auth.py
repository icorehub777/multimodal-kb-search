import unittest
from unittest.mock import patch

from kbsearch_importer.errors import ExternalServiceError
from kbsearch_importer.google_auth import get_dwd_access_token


class GoogleAuthTests(unittest.TestCase):
    def test_adc_refresh_failure_raises_domain_error(self):
        class FakeCredentials:
            def refresh(self, _request):
                raise RuntimeError("reauth required")

        with patch("google.auth.default", return_value=(FakeCredentials(), "project")):
            with self.assertRaisesRegex(ExternalServiceError, "Application Default Credentials"):
                get_dwd_access_token(
                    service_account_email="svc@example.com",
                    subject_email="user@example.com",
                )


if __name__ == "__main__":
    unittest.main()
