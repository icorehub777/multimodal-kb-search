import unittest
from unittest.mock import patch

from kbsearch_importer.qdrant_client_factory import build_qdrant_client


class QdrantClientFactoryTests(unittest.TestCase):
    @patch("qdrant_client.QdrantClient")
    def test_build_qdrant_client_omits_api_key_when_not_configured(self, qdrant_client_cls) -> None:
        build_qdrant_client("http://127.0.0.1:6333", None)

        qdrant_client_cls.assert_called_once_with(url="http://127.0.0.1:6333", timeout=60)

    @patch("qdrant_client.QdrantClient")
    def test_build_qdrant_client_passes_api_key_when_configured(self, qdrant_client_cls) -> None:
        build_qdrant_client("https://qdrant.example.com", "secret")

        qdrant_client_cls.assert_called_once_with(
            url="https://qdrant.example.com",
            api_key="secret",
            timeout=60,
        )


if __name__ == "__main__":
    unittest.main()
