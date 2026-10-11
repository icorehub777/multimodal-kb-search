import tempfile
import unittest
from pathlib import Path

from kbsearch_cli.full_text import (
    extract_full_text_keywords,
    locate_full_text_keyword_pages,
)


class FullTextKeywordTests(unittest.TestCase):
    def test_extract_full_text_keywords_preserves_positive_query_order(self):
        query = (
            "name contains 'Alpha' and fullText contains '推車' "
            "or fullText contains '安裝' and not fullText contains '草稿' "
            "and - fullText contains '忽略'"
        )

        self.assertEqual(extract_full_text_keywords(query), ["推車", "安裝"])

    def test_extract_full_text_keywords_decodes_escaped_quotes_and_backslashes(self):
        self.assertEqual(
            extract_full_text_keywords(r"fullText contains 'John\'s \\ cart'"),
            ["John's \\ cart"],
        )

    def test_locate_full_text_keyword_pages_uses_case_insensitive_literal_matches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            page_1 = root / "0001.txt"
            page_2 = root / "0002.txt"
            page_3 = root / "0003.txt"
            page_1.write_text("Alpha cart", encoding="utf-8")
            page_2.write_text("install ALPHA beta", encoding="utf-8")
            page_3.write_text("nothing relevant", encoding="utf-8")

            pages = locate_full_text_keyword_pages(
                [page_3, page_2, page_1],
                ["alpha", "beta", "alpha"],
            )

        self.assertEqual(
            [page.to_dict() for page in pages],
            [
                {"page_number": 1, "keyword": "alpha"},
                {"page_number": 2, "keyword": "alpha, beta"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
