import unittest
import os
from unittest import mock
from tempfile import TemporaryDirectory
from pathlib import Path

from PIL import Image

from app.dashscope_embedder import (
    DashScopeImageEmbeddingClient,
    DashScopePageEmbedder,
    _prepare_image_for_dashscope,
)
from app.errors import ExternalServiceError


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

    def test_prepare_image_keeps_small_image_unchanged(self):
        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "small.png"
            Image.new("RGB", (10, 10), "white").save(image_path, format="PNG")

            prepared = _prepare_image_for_dashscope(
                image_path,
                max_bytes=1_000_000,
                jpeg_quality=95,
                output_dir=Path(temp_dir) / "prepared",
            )

        self.assertEqual(prepared, image_path)

    def test_prepare_image_compresses_large_images_for_dashscope_limit(self):
        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "large.png"
            image = Image.frombytes("RGB", (1600, 1600), os.urandom(1600 * 1600 * 3))
            image.save(image_path, format="PNG")

            prepared = _prepare_image_for_dashscope(
                image_path,
                max_bytes=1_000_000,
                jpeg_quality=95,
                output_dir=Path(temp_dir) / "prepared",
            )

            self.assertEqual(prepared.suffix, ".jpg")
            self.assertLessEqual(prepared.stat().st_size, 1_000_000)

    def test_client_passes_local_file_path_to_dashscope(self):
        class FakeResponse:
            status_code = 200
            output = {"embeddings": [{"embedding": [0.1, 0.2, 0.3]}]}

        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "sample.png"
            Image.new("RGB", (10, 10)).save(image_path, format="PNG")
            with mock.patch(
                "dashscope.MultiModalEmbedding.call",
                return_value=FakeResponse(),
            ) as call:
                client = DashScopeImageEmbeddingClient(
                    api_key="key",
                    model="model",
                    dimension=3,
                    image_max_bytes=1_000_000,
                    jpeg_quality=95,
                )
                client.embed_image(image_path)

        self.assertEqual(call.call_args.kwargs["input"], [{"image": str(image_path.resolve())}])

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
                client = DashScopeImageEmbeddingClient(
                    api_key="key",
                    model="model",
                    dimension=3,
                    image_max_bytes=1_000_000,
                    jpeg_quality=95,
                )
                with self.assertRaises(ExternalServiceError):
                    client.embed_image(image_path)


if __name__ == "__main__":
    unittest.main()
