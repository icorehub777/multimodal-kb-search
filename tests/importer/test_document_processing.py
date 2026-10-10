import unittest
from pathlib import Path

from kbsearch_importer.document_processing import (
    UnsupportedDocumentTypeError,
    classify_document_type,
    page_png_path,
)


class DocumentProcessingTests(unittest.TestCase):
    def test_classify_document_type_supports_required_file_types(self) -> None:
        self.assertEqual(classify_document_type("application/pdf"), "pdf")
        self.assertEqual(
            classify_document_type(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            "word",
        )
        self.assertEqual(
            classify_document_type(
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            ),
            "powerpoint",
        )
        self.assertEqual(classify_document_type("text/plain"), "txt")
        self.assertEqual(classify_document_type("text/markdown"), "md")
        self.assertEqual(classify_document_type("image/png"), "image")
        self.assertEqual(classify_document_type("image/jpeg"), "image")
        self.assertEqual(classify_document_type("image/webp"), "image")
        self.assertEqual(classify_document_type("application/vnd.google-apps.document"), "pdf")
        self.assertEqual(classify_document_type("application/vnd.google-apps.presentation"), "pdf")

    def test_classify_document_type_rejects_excel(self) -> None:
        excel_mime_types = [
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.google-apps.spreadsheet",
        ]

        for mime_type in excel_mime_types:
            with self.subTest(mime_type=mime_type):
                with self.assertRaisesRegex(UnsupportedDocumentTypeError, "Excel"):
                    classify_document_type(mime_type)

    def test_page_png_path_uses_four_digit_numbering_from_one(self) -> None:
        self.assertEqual(page_png_path(Path("pages"), 1), Path("pages/0001.png"))
        self.assertEqual(page_png_path(Path("pages"), 12), Path("pages/0012.png"))
        self.assertEqual(page_png_path(Path("pages"), 100), Path("pages/0100.png"))

    def test_page_png_path_rejects_zero_page_number(self) -> None:
        with self.assertRaisesRegex(ValueError, "page_number"):
            page_png_path(Path("pages"), 0)


if __name__ == "__main__":
    unittest.main()
