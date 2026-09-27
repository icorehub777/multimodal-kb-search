import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.errors import ExternalServiceError
from app.google_auth import get_dwd_access_token


class GoogleAuthTests(unittest.TestCase):
    def test_dwd_refresh_failure_raises_domain_error(self):
        class FakeCredentials:
            service_account_email = "svc@example.com"

            def refresh(self, _request):
                raise RuntimeError("reauth required")

        with patch(
            "google.oauth2.service_account.Credentials.from_service_account_file",
            return_value=FakeCredentials(),
        ):
            with patch("app.google_auth.ensure_google_application_credentials", return_value="/tmp/key.json"):
                with self.assertRaisesRegex(ExternalServiceError, "Domain-Wide Delegation"):
                    get_dwd_access_token(
                        service_account_email="svc@example.com",
                        subject_email="user@example.com",
                    )

    def test_dwd_refresh_network_failure_mentions_network_dns(self):
        class FakeCredentials:
            service_account_email = "svc@example.com"

            def refresh(self, _request):
                raise RuntimeError("Failed to resolve 'oauth2.googleapis.com'")

        with patch(
            "google.oauth2.service_account.Credentials.from_service_account_file",
            return_value=FakeCredentials(),
        ):
            with patch("app.google_auth.ensure_google_application_credentials", return_value="/tmp/key.json"):
                with self.assertRaisesRegex(ExternalServiceError, "network/DNS"):
                    get_dwd_access_token(
                        service_account_email="svc@example.com",
                        subject_email="user@example.com",
                    )

    def test_dwd_refresh_returns_access_token(self):
        class FakeCredentials:
            service_account_email = "svc@example.com"
            token = "drive-token"
            expiry = datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc)

            def refresh(self, _request):
                return None

        with patch(
            "google.oauth2.service_account.Credentials.from_service_account_file",
            return_value=FakeCredentials(),
        ) as factory:
            with patch("app.google_auth.ensure_google_application_credentials", return_value="/tmp/key.json"):
                token = get_dwd_access_token(
                    service_account_email="svc@example.com",
                    subject_email="user@example.com",
                )

        self.assertEqual(token, "drive-token")
        factory.assert_called_once_with(
            "/tmp/key.json",
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
            subject="user@example.com",
        )


if __name__ == "__main__":
    unittest.main()
