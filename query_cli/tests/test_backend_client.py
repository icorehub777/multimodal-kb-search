import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kbsearch_cli.backend_client import SecureBackendClient
from kbsearch_cli.errors import ExternalServiceError, QueryCliError


class BackendClientTests(unittest.TestCase):
    def test_search_sends_image_bytes_instead_of_local_paths(self):
        captured = {}

        class FakeResponse:
            status_code = 200

            @staticmethod
            def json():
                return {"results": []}

        def fake_post(url, json, timeout):
            captured["url"] = url
            captured["json"] = json
            captured["timeout"] = timeout
            return FakeResponse()

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "sample.png"
            image_path.write_bytes(b"png-bytes")

            with patch("requests.post", side_effect=fake_post):
                SecureBackendClient("http://backend").search(
                    query="alpha",
                    image_paths=[image_path],
                    limit=5,
                    min_score=0.4,
                )

        self.assertEqual(captured["url"], "http://backend/search/vector")
        self.assertIsNone(captured["timeout"])
        self.assertNotIn("image_paths", captured["json"])
        self.assertEqual(captured["json"]["images"][0]["filename"], "sample.png")
        self.assertEqual(captured["json"]["images"][0]["mime_type"], "image/png")
        self.assertEqual(base64.b64decode(captured["json"]["images"][0]["base64_data"]), b"png-bytes")

    def test_search_uses_configured_timeout_when_provided(self):
        class FakeResponse:
            status_code = 200

            @staticmethod
            def json():
                return {"results": []}

        with patch("requests.post", return_value=FakeResponse()) as post:
            SecureBackendClient("http://backend", timeout_seconds=90).search(
                query="alpha",
                image_paths=[],
                limit=5,
                min_score=0.4,
            )

        self.assertEqual(post.call_args.kwargs["timeout"], 90)

    def test_search_wraps_unreachable_backend_errors(self):
        import requests

        with patch(
            "requests.post",
            side_effect=requests.RequestException("connection refused"),
        ):
            with self.assertRaisesRegex(
                ExternalServiceError,
                "Secure backend unreachable \\(http://backend/search/vector\\)",
            ):
                SecureBackendClient("http://backend").search(
                    query="alpha",
                    image_paths=[],
                    limit=5,
                    min_score=0.4,
                )

    def test_search_rejects_missing_image_paths(self):
        with self.assertRaisesRegex(QueryCliError, "Query image not found"):
            SecureBackendClient("http://backend").search(
                query="alpha",
                image_paths=[Path("C:/missing/sample.png")],
                limit=5,
                min_score=0.4,
            )


if __name__ == "__main__":
    unittest.main()
