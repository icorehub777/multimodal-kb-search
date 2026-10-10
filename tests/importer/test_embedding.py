import unittest

from kbsearch_importer.embedding import EmbeddingDimensionError, validate_embedding_vector


class EmbeddingTests(unittest.TestCase):
    def test_validate_embedding_vector_accepts_expected_dimension(self) -> None:
        vector = validate_embedding_vector([0.1, 0.2, 0.3], expected_dimension=3)

        self.assertEqual(vector, (0.1, 0.2, 0.3))

    def test_validate_embedding_vector_rejects_unexpected_dimension(self) -> None:
        with self.assertRaisesRegex(EmbeddingDimensionError, "dimension"):
            validate_embedding_vector([0.1, 0.2], expected_dimension=3)


if __name__ == "__main__":
    unittest.main()
