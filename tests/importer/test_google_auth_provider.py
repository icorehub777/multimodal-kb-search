import unittest

from kbsearch_importer.google_auth import GoogleDriveServiceProvider


class GoogleDriveServiceProviderTests(unittest.TestCase):
    def test_get_service_reuses_unexpired_service(self):
        calls = []

        def token_factory():
            calls.append("token")
            return ("token-1", 1000)

        def service_builder(token):
            return {"token": token}

        provider = GoogleDriveServiceProvider(
            service_account_email="svc@example.com",
            subject_email="user@example.com",
            token_factory=token_factory,
            service_builder=service_builder,
            clock=lambda: 100,
        )

        self.assertIs(provider.get_service(), provider.get_service())
        self.assertEqual(calls, ["token"])

    def test_get_service_refreshes_when_token_is_near_expiry(self):
        tokens = [("token-1", 1000), ("token-2", 2000)]

        provider = GoogleDriveServiceProvider(
            service_account_email="svc@example.com",
            subject_email="user@example.com",
            token_factory=lambda: tokens.pop(0),
            service_builder=lambda token: {"token": token},
            clock=lambda: 800,
            refresh_margin_seconds=300,
        )

        self.assertEqual(provider.get_service()["token"], "token-1")
        self.assertEqual(provider.get_service()["token"], "token-2")

    def test_files_checks_token_expiry_each_time(self):
        now = 100
        tokens = [("token-1", 1000), ("token-2", 2000)]

        class FakeService:
            def __init__(self, token):
                self.token = token

            def files(self):
                return f"files-{self.token}"

        provider = GoogleDriveServiceProvider(
            service_account_email="svc@example.com",
            subject_email="user@example.com",
            token_factory=lambda: tokens.pop(0),
            service_builder=FakeService,
            clock=lambda: now,
            refresh_margin_seconds=300,
        )

        self.assertEqual(provider.files(), "files-token-1")
        now = 800
        self.assertEqual(provider.files(), "files-token-2")


if __name__ == "__main__":
    unittest.main()
