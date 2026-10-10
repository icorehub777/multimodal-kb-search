import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kbsearch_cli.backend_client import SecureBackendClient
from kbsearch_cli.errors import ConfigError, ExternalServiceError, QueryCliError, QueryInputError


class BackendClientTests(unittest.TestCase):
    def test_search_parses_valid_response_into_typed_models(self):
        response = type(
            "Response",
            (),
            {
                "status_code": 200,
                "json": lambda self: {
                    "results": [
                        {
                            "google_file_id": "file-1",
                            "source_name": "Manual.pdf",
                            "source_location": "Drive/Manual.pdf",
                            "source_url": "https://drive/file-1",
                            "google_drive_version": "7",
                            "google_drive_modified_time": "2026-05-24T00:00:00Z",
                            "score": 0.91,
                            "pages": [{"page_number": 3, "score": 0.88}],
                        }
                    ]
                },
            },
        )()

        with patch("requests.post", return_value=response):
            results = SecureBackendClient("http://backend", "backend-secret").search(
                "alpha", [], 5, None
            )

        self.assertEqual(results[0].google_file_id, "file-1")
        self.assertEqual(results[0].pages[0].page_number, 3)

    def test_search_sends_image_bytes_instead_of_local_paths(self):
        captured = {}

        class FakeResponse:
            status_code = 200

            @staticmethod
            def json():
                return {"results": []}

        def fake_post(url, json, headers, timeout):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            captured["timeout"] = timeout
            return FakeResponse()

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "sample.png"
            image_path.write_bytes(b"png-bytes")

            with patch("requests.post", side_effect=fake_post):
                SecureBackendClient("http://backend", "backend-secret").search(
                    query="alpha",
                    image_paths=[image_path],
                    limit=5,
                    min_score=0.4,
                )

        self.assertEqual(captured["url"], "http://backend/search/vector")
        self.assertEqual(captured["headers"], {"X-API-Key": "backend-secret"})
        self.assertEqual(captured["timeout"], (10.0, None))
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
            SecureBackendClient(
                "http://backend", "backend-secret", timeout_seconds=90
            ).search(
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
                SecureBackendClient("http://backend", "backend-secret").search(
                    query="alpha",
                    image_paths=[],
                    limit=5,
                    min_score=0.4,
                )

    def test_search_rejects_missing_image_paths(self):
        with self.assertRaisesRegex(QueryCliError, "Query image not found"):
            SecureBackendClient("http://backend", "backend-secret").search(
                query="alpha",
                image_paths=[Path("C:/missing/sample.png")],
                limit=5,
                min_score=0.4,
            )

    def test_search_rejects_non_json_response(self):
        response = type(
            "Response",
            (),
            {"status_code": 200, "json": lambda self: (_ for _ in ()).throw(ValueError())},
        )()
        with patch("requests.post", return_value=response), self.assertRaisesRegex(
            ExternalServiceError, "non-JSON"
        ):
            SecureBackendClient("http://backend", "backend-secret").search(
                "alpha", [], 5, None
            )

    def test_search_rejects_invalid_response_contract(self):
        response = type(
            "Response",
            (),
            {"status_code": 200, "json": lambda self: {"results": {}}},
        )()
        with patch("requests.post", return_value=response), self.assertRaisesRegex(
            ExternalServiceError, "invalid response"
        ):
            SecureBackendClient("http://backend", "backend-secret").search(
                "alpha", [], 5, None
            )

    def test_search_maps_request_errors_to_query_input_error(self):
        response = type(
            "Response",
            (),
            {
                "status_code": 400,
                "json": lambda self: {
                    "error": "invalid_request",
                    "field": "limit",
                    "message": "limit must be between 1 and 100.",
                },
            },
        )()

        with patch("requests.post", return_value=response), self.assertRaisesRegex(
            QueryInputError, "limit must be between 1 and 100"
        ):
            SecureBackendClient("http://backend", "backend-secret").search(
                "alpha", [], 101, None
            )

    def test_search_maps_authentication_error_to_config_error(self):
        response = type(
            "Response",
            (),
            {
                "status_code": 401,
                "json": lambda self: {
                    "error": "authentication",
                    "message": "API key is missing or invalid.",
                },
            },
        )()

        with patch("requests.post", return_value=response), self.assertRaisesRegex(
            ConfigError, "API key"
        ):
            SecureBackendClient("http://backend", "backend-secret").search(
                "alpha", [], 5, None
            )


if __name__ == "__main__":
    unittest.main()
