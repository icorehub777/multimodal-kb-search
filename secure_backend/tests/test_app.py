import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from kbsearch_secure_backend.app import create_app
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

    def test_create_app_initializes_default_service_once(self):
        with patch("kbsearch_secure_backend.app.load_backend_config") as load_config, patch(
            "kbsearch_secure_backend.app.create_vector_search_service",
            return_value=FakeVectorSearchService(),
        ) as create_service:
            app = create_app()
            client = TestClient(app)
            response_1 = client.post("/search/vector", json={"query": "alpha", "images": [], "limit": 5, "min_score": 0.5})
            response_2 = client.post("/search/vector", json={"query": "beta", "images": [], "limit": 5, "min_score": 0.5})

        load_config.assert_called_once()
        create_service.assert_called_once_with(load_config.return_value)
        self.assertEqual(response_1.status_code, 200)
        self.assertEqual(response_2.status_code, 200)


if __name__ == "__main__":
    unittest.main()
