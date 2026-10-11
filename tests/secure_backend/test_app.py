import logging
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from starlette.testclient import TestClient

from kbsearch_backend.config import BackendConfig
from kbsearch_backend.errors import ExternalServiceError, InvalidRequestError, PayloadTooLargeError
from kbsearch_backend.factory import _run_startup_probe, create_app
from kbsearch_backend.logging_config import LOGGER_NAME, configure_backend_logging
from kbsearch_backend.models import PageSearchResult, VectorFileSearchResult
from kbsearch_backend.startup_probe import StartupProbeResult


API_KEY = "test-api-key"
AUTH_HEADERS = {"X-API-Key": API_KEY}


class FakeVectorSearchService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def search(self, query, images, limit, min_score):
        if self.error is not None:
            raise self.error
        return [
            VectorFileSearchResult(
                google_file_id="file-1",
                source_name="Spec.pdf",
                source_location="Drive/Spec.pdf",
                source_url="https://drive/file-1",
                google_drive_version="7",
                google_drive_modified_time="2026-05-24T00:00:00Z",
                score=0.9,
                pages=[
                    PageSearchResult(
                        google_file_id="file-1",
                        source_name="Spec.pdf",
                        source_location="Drive/Spec.pdf",
                        source_url="https://drive/file-1",
                        google_drive_version="7",
                        google_drive_modified_time="2026-05-24T00:00:00Z",
                        page_number=1,
                        score=0.9,
                    )
                ],
            )
        ]


def _backend_config(log_file_path: Path, **overrides) -> BackendConfig:
    values = {
        "secure_backend_api_key": API_KEY,
        "dashscope_api_key": "dashscope-key",
        "dashscope_embedding_model": "qwen3-vl-embedding",
        "vector_size": 4,
        "dashscope_image_max_bytes": 9_728_000,
        "dashscope_jpeg_quality": 95,
        "qdrant_url": "https://qdrant.example.com",
        "qdrant_api_key": "qdrant-key",
        "qdrant_collection": "kbsearch",
        "log_file_path": log_file_path,
        "max_query_length": 4_000,
        "max_images": 5,
        "max_search_limit": 100,
        "log_level": "INFO",
    }
    values.update(overrides)
    return BackendConfig(**values)


class AppTests(unittest.TestCase):
    def test_all_endpoints_require_api_key(self):
        client = self._client()
        responses = (
            client.get("/healthz"),
            client.post("/search/vector", json={"query": "alpha"}),
        )

        for response in responses:
            self.assertEqual(response.status_code, 401)
            self.assertEqual(
                response.json(),
                {"error": "authentication", "message": "API key is missing or invalid."},
            )

    def test_healthz_returns_ok_with_api_key(self):
        response = self._client().get("/healthz", headers=AUTH_HEADERS)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_search_vector_returns_response_model(self):
        response = self._client().post(
            "/search/vector",
            headers=AUTH_HEADERS,
            json={"query": "alpha", "images": [], "limit": 5, "min_score": 0.5},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["google_file_id"], "file-1")
        self.assertEqual(response.json()["results"][0]["pages"][0]["page_number"], 1)

    def test_request_requires_query_or_images(self):
        response = self._client().post(
            "/search/vector",
            headers=AUTH_HEADERS,
            json={"query": "  ", "images": []},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_request")
        self.assertEqual(response.json()["field"], "query")

    def test_malformed_json_returns_actionable_message_without_numeric_field(self):
        response = self._client().post(
            "/search/vector", headers={**AUTH_HEADERS, "Content-Type": "application/json"},
            content='{"query":',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {
            "error": "invalid_request", "message": "Request body must be valid JSON.",
        })

    def test_request_uses_configured_query_image_and_limit_bounds(self):
        config = self._config(max_query_length=5, max_images=1, max_search_limit=2)
        client = self._client(config=config)
        cases = (
            ({"query": "123456"}, "query", "5"),
            (
                {
                    "images": [
                        {"filename": "a.png", "mime_type": "image/png", "base64_data": "YQ=="},
                        {"filename": "b.png", "mime_type": "image/png", "base64_data": "Yg=="},
                    ]
                },
                "images",
                "1",
            ),
            ({"query": "alpha", "limit": 3}, "limit", "2"),
        )
        for payload, field, configured_limit in cases:
            with self.subTest(field=field):
                response = client.post("/search/vector", headers=AUTH_HEADERS, json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"], "invalid_request")
                self.assertEqual(response.json()["field"], field)
                self.assertIn(configured_limit, response.json()["message"])

    def test_request_rejects_invalid_min_score_with_actionable_message(self):
        response = self._client().post(
            "/search/vector",
            headers=AUTH_HEADERS,
            json={"query": "alpha", "min_score": 2},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["field"], "min_score")
        self.assertIn("-1", response.json()["message"])
        self.assertIn("1", response.json()["message"])

    def test_domain_errors_use_stable_response_contract(self):
        cases = (
            (InvalidRequestError("Invalid image payload.", field="images"), 400, "invalid_request"),
            (PayloadTooLargeError("Image exceeds processing limit.", field="images"), 413, "payload_too_large"),
            (ExternalServiceError("raw upstream detail"), 502, "external_service"),
        )
        for error, status_code, error_code in cases:
            with self.subTest(error_code=error_code):
                response = self._client(FakeVectorSearchService(error)).post(
                    "/search/vector", headers=AUTH_HEADERS, json={"query": "alpha"}
                )
                self.assertEqual(response.status_code, status_code)
                self.assertEqual(response.json()["error"], error_code)
                if error_code == "external_service":
                    self.assertNotIn("raw upstream detail", response.text)

    def test_unexpected_error_returns_safe_internal_response(self):
        response = self._client(
            FakeVectorSearchService(RuntimeError("secret internal detail")),
            raise_server_exceptions=False,
        ).post("/search/vector", headers=AUTH_HEADERS, json={"query": "alpha"})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"error": "internal", "message": "An internal error occurred."},
        )
        self.assertNotIn("secret internal detail", response.text)

    def test_search_vector_writes_application_log_file(self):
        temp_dir = self._create_temp_dir_with_log_cleanup()
        log_path = temp_dir / "logs" / "secure_backend.log"
        client = TestClient(
            create_app(service=FakeVectorSearchService(), config=_backend_config(log_path))
        )
        response = client.post(
            "/search/vector",
            headers=AUTH_HEADERS,
            json={"query": "alpha", "images": [], "limit": 5, "min_score": 0.5},
        )

        log_text = log_path.read_text(encoding="utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("search_vector succeeded", log_text)
        self.assertIn("limit=5", log_text)

    def test_create_app_initializes_default_service_once(self):
        temp_dir = self._create_temp_dir_with_log_cleanup()
        config = _backend_config(temp_dir / "secure_backend.log")
        with patch("kbsearch_backend.factory.load_backend_config", return_value=config) as load_config, patch(
            "kbsearch_backend.factory._run_startup_probe",
        ), patch(
            "kbsearch_backend.factory.create_vector_search_service",
            return_value=FakeVectorSearchService(),
        ) as create_service:
            client = TestClient(create_app())
            response_1 = client.post(
                "/search/vector", headers=AUTH_HEADERS, json={"query": "alpha"}
            )
            response_2 = client.post(
                "/search/vector", headers=AUTH_HEADERS, json={"query": "beta"}
            )

        load_config.assert_called_once()
        create_service.assert_called_once_with(config)
        self.assertEqual(response_1.status_code, 200)
        self.assertEqual(response_2.status_code, 200)

    def test_run_startup_probe_logs_failure_and_success(self):
        temp_dir = self._create_temp_dir_with_log_cleanup()
        log_path = temp_dir / "secure_backend.log"
        logger = configure_backend_logging(log_path)
        config = _backend_config(log_path)

        with patch("kbsearch_backend.factory.probe_startup_environment", side_effect=RuntimeError("unavailable")):
            with self.assertRaises(RuntimeError):
                _run_startup_probe(config, logger)
        with patch(
            "kbsearch_backend.factory.probe_startup_environment",
            return_value=StartupProbeResult(
                dashscope_model="qwen3-vl-embedding",
                dashscope_dimension=4,
                qdrant_collection="kbsearch",
                qdrant_host="qdrant.example.com",
                qdrant_points_count=3,
                qdrant_vector_size=4,
            ),
        ):
            _run_startup_probe(config, logger)

        log_text = log_path.read_text(encoding="utf-8")
        self.assertIn("startup_probe failed", log_text)
        self.assertIn("startup_probe succeeded", log_text)

    def _config(self, **overrides) -> BackendConfig:
        temp_dir = self._create_temp_dir_with_log_cleanup()
        return _backend_config(temp_dir / "secure_backend.log", **overrides)

    def _client(
        self,
        service: FakeVectorSearchService | None = None,
        *,
        config: BackendConfig | None = None,
        raise_server_exceptions: bool = True,
    ) -> TestClient:
        effective_config = config or self._config()
        return TestClient(
            create_app(service=service or FakeVectorSearchService(), config=effective_config),
            raise_server_exceptions=raise_server_exceptions,
        )

    def _create_temp_dir_with_log_cleanup(self) -> Path:
        temp_dir = TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(self._close_log_handlers)
        return Path(temp_dir.name)

    def _close_log_handlers(self) -> None:
        logger = logging.getLogger(LOGGER_NAME)
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)


if __name__ == "__main__":
    unittest.main()
