import unittest
import base64
import os
from unittest import mock
from tempfile import TemporaryDirectory
from pathlib import Path

from PIL import Image

from kbsearch_importer.dashscope_embedder import (
    MAX_DASHSCOPE_IMAGE_BYTES,
    DashScopePageEmbedder,
    _image_data_uri,
)
from kbsearch_importer.errors import ExternalServiceError


class FakeEmbeddingClient:
    def __init__(self):
        self.calls = []

    def embed_image(self, image_path):
        self.calls.append(image_path)
        return [0.1, 0.2, 0.3]


class DashScopePageEmbedderTests(unittest.TestCase):
    def test_embed_page_image_delegates_and_validates_dimension(self):
        client = FakeEmbeddingClient()
        embedder = DashScopePageEmbedder(client=client, expected_dimension=3)

        vector = embedder.embed_page_image(Path("01.png"))

        self.assertEqual(vector, [0.1, 0.2, 0.3])
        self.assertEqual(client.calls, [Path("01.png")])

    def test_image_data_uri_compresses_large_images_for_dashscope_limit(self):
        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "large.png"
            image = Image.frombytes("RGB", (1600, 1600), os.urandom(1600 * 1600 * 3))
            image.save(image_path, format="PNG")

            data_uri = _image_data_uri(image_path)

        header, encoded = data_uri.split(",", 1)
        payload = base64.b64decode(encoded)
        self.assertEqual(header, "data:image/jpeg;base64")
        self.assertLessEqual(len(payload), MAX_DASHSCOPE_IMAGE_BYTES)

    def test_dashscope_failure_raises_external_service_error(self):
        class FakeResponse:
            status_code = 400
            code = "InvalidParameter"
            message = "bad image"
            output = None

        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "sample.png"
            Image.new("RGB", (1, 1)).save(image_path, format="PNG")

            with mock.patch(
                "dashscope.MultiModalEmbedding.call",
                return_value=FakeResponse(),
            ):
                from kbsearch_importer.dashscope_embedder import DashScopeImageEmbeddingClient

                client = DashScopeImageEmbeddingClient(api_key="key", model="model", dimension=3)
                with self.assertRaises(ExternalServiceError):
                    client.embed_image(image_path)


if __name__ == "__main__":
    unittest.main()
