import base64
import unittest
from unittest.mock import patch

from kbsearch_secure_backend.embedding import _image_data_uri_from_payload
from kbsearch_secure_backend.models import QueryImage


class EmbeddingTests(unittest.TestCase):
    def test_image_data_uri_from_payload_uses_request_bytes(self):
        image = QueryImage(
            filename="sample.png",
            mime_type="image/png",
            base64_data=base64.b64encode(b"png-bytes").decode("ascii"),
        )

        self.assertEqual(_image_data_uri_from_payload(image), "data:image/png;base64,cG5nLWJ5dGVz")

    def test_image_data_uri_from_payload_does_not_reencode_small_payload(self):
        image = QueryImage(
            filename="sample.png",
            mime_type="image/png",
            base64_data=" cG5nLWJ5dGVz ",
        )

        with patch("kbsearch_secure_backend.embedding.base64.b64encode") as encode:
            self.assertEqual(_image_data_uri_from_payload(image), "data:image/png;base64,cG5nLWJ5dGVz")

        encode.assert_not_called()

    def test_image_data_uri_from_payload_compresses_large_payload(self):
        image = QueryImage(
            filename="large.png",
            mime_type="image/png",
            base64_data=base64.b64encode(b"x" * 10).decode("ascii"),
        )

        with patch("kbsearch_secure_backend.embedding.MAX_DASHSCOPE_IMAGE_BYTES", 1), patch(
            "kbsearch_secure_backend.embedding._compress_image_bytes_for_dashscope",
            return_value=b"jpg",
        ):
            self.assertEqual(_image_data_uri_from_payload(image), "data:image/jpeg;base64,anBn")


if __name__ == "__main__":
    unittest.main()
