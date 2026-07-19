import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.errors import InvalidRequestError
from app.factory import _http_exception_from_error, _run_startup_probe, create_app
from app.logging_config import LOGGER_NAME
from app.models import PageSearchResult, VectorFileSearchResult
from app.config import BackendConfig


class FakeVectorSearchService:
    def search(self, query, images, limit, min_score):
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


class AppTests(unittest.TestCase):
    def test_healthz_returns_ok(self):
        client = TestClient(create_app(service=FakeVectorSearchService()))

        response = client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_search_vector_returns_response_model(self):
        client = TestClient(create_app(service=FakeVectorSearchService()))

        response = client.post(
            "/search/vector",
            json={"query": "alpha", "images": [], "limit": 5, "min_score": 0.5},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["google_file_id"], "file-1")
        self.assertEqual(response.json()["results"][0]["pages"][0]["page_number"], 1)

    def test_invalid_request_error_maps_to_400_response_detail(self):
        response_error = _http_exception_from_error(InvalidRequestError("Invalid image payload: broken.jpg"))

        self.assertEqual(response_error.status_code, 400)
        self.assertEqual(
            response_error.detail,
            {
                "error": "InvalidRequestError",
                "message": "Invalid image payload: broken.jpg",
            },
        )

    def test_search_vector_writes_application_log_file(self):
        temp_dir = self._create_temp_dir_with_log_cleanup()
        log_path = temp_dir / "logs" / "secure_backend.log"
        client = TestClient(create_app(service=FakeVectorSearchService(), log_file_path=log_path))

        response = client.post(
            "/search/vector",
            json={"query": "alpha", "images": [], "limit": 5, "min_score": 0.5},
        )

        log_text = log_path.read_text(encoding="utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("search_vector succeeded", log_text)
        self.assertIn("limit=5", log_text)

    def test_create_app_uses_explicit_log_file_path_with_default_service(self):
        temp_dir = self._create_temp_dir_with_log_cleanup()
        config_log_path = temp_dir / "config" / "secure_backend.log"
        explicit_log_path = temp_dir / "explicit" / "secure_backend.log"
        with patch("app.factory.load_backend_config") as load_config, patch(
            "app.factory._run_startup_probe",
        ), patch(
            "app.factory.create_vector_search_service",
            return_value=FakeVectorSearchService(),
        ):
            load_config.return_value = SimpleNamespace(log_file_path=config_log_path)
            client = TestClient(create_app(log_file_path=explicit_log_path))

            response = client.post(
                "/search/vector", json={"query": "alpha", "images": [], "limit": 5, "min_score": 0.5}
            )

            log_text = explicit_log_path.read_text(encoding="utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("search_vector succeeded", log_text)
        self.assertFalse(config_log_path.exists())

    def test_create_app_initializes_default_service_once(self):
        temp_dir = self._create_temp_dir_with_log_cleanup()
        with patch("app.factory.load_backend_config") as load_config, patch(
            "app.factory._run_startup_probe",
        ), patch(
            "app.factory.create_vector_search_service",
            return_value=FakeVectorSearchService(),
        ) as create_service:
            load_config.return_value.log_file_path = temp_dir / "secure_backend.log"
            app = create_app()
            client = TestClient(app)
            response_1 = client.post(
                "/search/vector", json={"query": "alpha", "images": [], "limit": 5, "min_score": 0.5}
            )
            response_2 = client.post(
                "/search/vector", json={"query": "beta", "images": [], "limit": 5, "min_score": 0.5}
            )

        load_config.assert_called_once()
        create_service.assert_called_once_with(load_config.return_value)
        self.assertEqual(response_1.status_code, 200)
        self.assertEqual(response_2.status_code, 200)

    def test_run_startup_probe_logs_failure(self):
        temp_dir = self._create_temp_dir_with_log_cleanup()
        log_path = temp_dir / "secure_backend.log"
        configure_backend_logging = __import__(
            "app.logging_config", fromlist=["configure_backend_logging"]
        ).configure_backend_logging
        logger = configure_backend_logging(log_path)
        config = BackendConfig(
            dashscope_api_key="dashscope-key",
            dashscope_embedding_model="qwen3-vl-embedding",
            dashscope_vector_size=4,
            dashscope_image_max_bytes=9_728_000,
            dashscope_jpeg_quality=95,
            qdrant_url="https://qdrant.example.com",
            qdrant_api_key="qdrant-key",
            qdrant_collection="kbsearch",
            qdrant_vector_size=4,
            log_file_path=log_path,
        )
        with patch(
            "app.factory.probe_startup_environment",
            side_effect=RuntimeError("qdrant unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                _run_startup_probe(config, logger)

        log_text = log_path.read_text(encoding="utf-8")
        self.assertIn("startup_probe failed", log_text)
        self.assertIn("qdrant unavailable", log_text)

    def test_run_startup_probe_logs_success(self):
        temp_dir = self._create_temp_dir_with_log_cleanup()
        log_path = temp_dir / "secure_backend.log"
        configure_backend_logging = __import__(
            "app.logging_config", fromlist=["configure_backend_logging"]
        ).configure_backend_logging
        logger = configure_backend_logging(log_path)
        config = BackendConfig(
            dashscope_api_key="dashscope-key",
            dashscope_embedding_model="qwen3-vl-embedding",
            dashscope_vector_size=4,
            dashscope_image_max_bytes=9_728_000,
            dashscope_jpeg_quality=95,
            qdrant_url="https://qdrant.example.com",
            qdrant_api_key="qdrant-key",
            qdrant_collection="kbsearch",
            qdrant_vector_size=4,
            log_file_path=log_path,
        )
        with patch(
            "app.factory.probe_startup_environment",
            return_value=__import__(
                "app.startup_probe", fromlist=["StartupProbeResult"]
            ).StartupProbeResult(
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
        self.assertIn("startup_probe succeeded", log_text)
        self.assertIn("qdrant_points=3", log_text)

    def test_create_app_raises_when_startup_probe_fails(self):
        temp_dir = self._create_temp_dir_with_log_cleanup()
        log_path = temp_dir / "secure_backend.log"
        with patch("app.factory.load_backend_config") as load_config, patch(
            "app.factory._run_startup_probe",
            side_effect=RuntimeError("qdrant unavailable"),
        ):
            load_config.return_value = SimpleNamespace(log_file_path=log_path)

            with self.assertRaises(RuntimeError):
                create_app(log_file_path=log_path)

    def _create_temp_dir_with_log_cleanup(self):
        temp_dir = TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(self._close_log_handlers)
        return Path(temp_dir.name)

    def _close_log_handlers(self):
        import logging

        logger = logging.getLogger(LOGGER_NAME)
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)


if __name__ == "__main__":
    unittest.main()
