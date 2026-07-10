from __future__ import annotations

from pathlib import Path

from kbsearch_cli.models import FullTextPageSearchResult


_FULL_TEXT_FIELD = "fullText"
_CONTAINS_OPERATOR = "contains"


def extract_full_text_keywords(drive_query: str | None) -> list[str]:
    if not drive_query:
        return []

    keywords: list[str] = []
    index = 0
    while index < len(drive_query):
        field_index = _find_word(drive_query, _FULL_TEXT_FIELD, index)
        if field_index < 0:
            break
        index = field_index + len(_FULL_TEXT_FIELD)
        contains_index = _skip_whitespace(drive_query, index)
        if not _matches_word_at(drive_query, _CONTAINS_OPERATOR, contains_index):
            continue
        quote_index = _skip_whitespace(
            drive_query,
            contains_index + len(_CONTAINS_OPERATOR),
        )
        if quote_index >= len(drive_query) or drive_query[quote_index] != "'":
            continue
        keyword, next_index = _parse_quoted_string(drive_query, quote_index)
        index = next_index
        if keyword and not _is_negated_full_text_clause(drive_query, field_index):
            keywords.append(keyword)
    return keywords


def locate_full_text_keyword_pages(
    text_paths: list[Path],
    keywords: list[str],
) -> list[FullTextPageSearchResult]:
    ordered_keywords = list(dict.fromkeys(keyword for keyword in keywords if keyword))
    if not ordered_keywords:
        return []

    pages: list[FullTextPageSearchResult] = []
    for text_path in sorted(text_paths, key=_page_sort_key):
        page_number = _page_number_from_text_path(text_path)
        if page_number is None:
            continue
        text = text_path.read_text(encoding="utf-8").casefold()
        matched_keywords = [
            keyword
            for keyword in ordered_keywords
            if keyword.casefold() in text
        ]
        if matched_keywords:
            pages.append(
                FullTextPageSearchResult(
                    page_number=page_number,
                    keyword=", ".join(matched_keywords),
                )
            )
    return pages


def _find_word(text: str, word: str, start: int) -> int:
    lower_text = text.casefold()
    lower_word = word.casefold()
    index = lower_text.find(lower_word, start)
    while index >= 0:
        end = index + len(word)
        if _is_word_boundary(text, index - 1) and _is_word_boundary(text, end):
            return index
        index = lower_text.find(lower_word, end)
    return -1


def _matches_word_at(text: str, word: str, index: int) -> bool:
    end = index + len(word)
    return (
        text[index:end].casefold() == word.casefold()
        and _is_word_boundary(text, index - 1)
        and _is_word_boundary(text, end)
    )


def _is_word_boundary(text: str, index: int) -> bool:
    if index < 0 or index >= len(text):
        return True
    character = text[index]
    return not (character.isalnum() or character == "_")


def _skip_whitespace(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _parse_quoted_string(text: str, quote_index: int) -> tuple[str, int]:
    characters: list[str] = []
    index = quote_index + 1
    while index < len(text):
        character = text[index]
        if character == "\\" and index + 1 < len(text):
            characters.append(text[index + 1])
            index += 2
            continue
        if character == "'":
            return "".join(characters), index + 1
        characters.append(character)
        index += 1
    return "".join(characters), index


def _is_negated_full_text_clause(text: str, field_index: int) -> bool:
    index = field_index - 1
    while index >= 0 and text[index].isspace():
        index -= 1
    if index >= 0 and text[index] == "-":
        return True
    while index >= 0 and text[index] in "(\t\r\n ":
        index -= 1
    end = index + 1
    while index >= 0 and (text[index].isalpha() or text[index] == "_"):
        index -= 1
    return text[index + 1:end].casefold() == "not"


def _page_sort_key(path: Path) -> tuple[int, str]:
    page_number = _page_number_from_text_path(path)
    return (page_number if page_number is not None else 10**9, path.name)


def _page_number_from_text_path(path: Path) -> int | None:
    try:
        return int(path.stem)
    except ValueError:
        return None
