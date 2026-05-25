import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from kbsearch_secure_backend.app import create_app
from kbsearch_secure_backend.logging_config import LOGGER_NAME
from kbsearch_secure_backend.models import PageSearchResult, VectorFileSearchResult


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
                        page_image_path="pages/01.png",
                        source_file_path="source/Spec.pdf",
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
        with patch("kbsearch_secure_backend.app.load_backend_config") as load_config, patch(
            "kbsearch_secure_backend.app.create_vector_search_service",
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
        with patch("kbsearch_secure_backend.app.load_backend_config") as load_config, patch(
            "kbsearch_secure_backend.app.create_vector_search_service",
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
