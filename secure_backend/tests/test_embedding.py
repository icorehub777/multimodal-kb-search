import base64
from io import BytesIO
import unittest
from unittest.mock import ANY, MagicMock, patch

from app.errors import InvalidRequestError
from app.embedding import (
    DashScopeQueryEmbeddingClient,
    _image_data_uri_from_payload,
    _normalize_image_bytes_for_dashscope,
)
from app.models import QueryImage


class EmbeddingTests(unittest.TestCase):
    def test_image_data_uri_from_payload_normalizes_small_image_as_png(self):
        source = _jpeg_bytes((1, 1))
        image = QueryImage(
            filename="sample.jpg",
            mime_type="image/jpeg",
            base64_data=base64.b64encode(source).decode("ascii"),
        )

        data_uri = _image_data_uri_from_payload(image, max_bytes=1_000_000, jpeg_quality=95)

        self.assertTrue(data_uri.startswith("data:image/png;base64,"))
        self.assertNotEqual(data_uri, f"data:image/png;base64,{image.base64_data}")

    def test_image_data_uri_from_payload_strips_base64_whitespace(self):
        source = _png_bytes((1, 1))
        image = QueryImage(
            filename="sample.png",
            mime_type="image/png",
            base64_data=f" {base64.b64encode(source).decode('ascii')} ",
        )

        self.assertTrue(
            _image_data_uri_from_payload(
                image,
                max_bytes=1_000_000,
                jpeg_quality=95,
            ).startswith("data:image/png;base64,")
        )

    def test_normalize_image_bytes_applies_exif_orientation(self):
        from PIL import Image

        source = Image.new("RGB", (2, 3), color=(255, 0, 0))
        exif = source.getexif()
        exif[274] = 6
        buffer = BytesIO()
        source.save(buffer, format="JPEG", exif=exif)

        normalized = _normalize_image_bytes_for_dashscope(buffer.getvalue())

        with Image.open(BytesIO(normalized)) as rendered:
            self.assertEqual(rendered.size, (3, 2))

    def test_image_data_uri_from_payload_compresses_large_payload(self):
        source = _png_bytes((1, 1))
        image = QueryImage(
            filename="large.png",
            mime_type="image/png",
            base64_data=base64.b64encode(source).decode("ascii"),
        )

        with patch(
            "app.embedding._compress_image_bytes_for_dashscope",
            return_value=b"jpg",
        ) as compress:
            self.assertEqual(
                _image_data_uri_from_payload(image, max_bytes=1, jpeg_quality=90),
                "data:image/jpeg;base64,anBn",
            )

        compress.assert_called_once_with(ANY, max_bytes=1, jpeg_quality=90)

    def test_image_data_uri_from_payload_rejects_invalid_base64(self):
        image = QueryImage(
            filename="broken.jpg",
            mime_type="image/jpeg",
            base64_data="not-base64",
        )

        with self.assertRaises(InvalidRequestError) as ctx:
            _image_data_uri_from_payload(image, max_bytes=1_000_000, jpeg_quality=95)

        self.assertIn("Invalid base64 image payload: broken.jpg", str(ctx.exception))

    def test_image_data_uri_from_payload_rejects_unrecognized_image_content(self):
        image = QueryImage(
            filename="broken.jpg",
            mime_type="image/jpeg",
            base64_data=base64.b64encode(b"not image bytes").decode("ascii"),
        )

        with self.assertRaises(InvalidRequestError) as ctx:
            _image_data_uri_from_payload(image, max_bytes=1_000_000, jpeg_quality=95)

        self.assertIn("Invalid image payload: broken.jpg", str(ctx.exception))

    def test_client_uses_configured_image_preparation_settings(self):
        image = QueryImage(
            filename="sample.png",
            mime_type="image/png",
            base64_data=base64.b64encode(_png_bytes((1, 1))).decode("ascii"),
        )
        response = MagicMock(
            status_code=200,
            output={"embeddings": [{"embedding": [0.1, 0.2]}]},
        )
        client = DashScopeQueryEmbeddingClient(
            api_key="key",
            model="model",
            dimension=2,
            image_max_bytes=9_000_000,
            jpeg_quality=90,
        )

        with patch("dashscope.MultiModalEmbedding.call", return_value=response), patch(
            "app.embedding._image_data_uri_from_payload",
            return_value="data:image/png;base64,cG5n",
        ) as prepare:
            client.embed_query("", [image])

        prepare.assert_called_once_with(
            image,
            max_bytes=9_000_000,
            jpeg_quality=90,
        )


def _png_bytes(size: tuple[int, int]) -> bytes:
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", size, color=(255, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def _jpeg_bytes(size: tuple[int, int]) -> bytes:
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", size, color=(255, 0, 0)).save(buffer, format="JPEG")
    return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
