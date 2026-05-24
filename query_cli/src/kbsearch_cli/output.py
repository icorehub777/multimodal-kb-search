from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from kbsearch_cli.models import FullTextSearchResult, QueryResultBundle, VectorFileSearchResult


INVALID_FILENAME_PATTERN = re.compile(r'[<>:"/\\\\|?*]+')


def safe_path_name(name: str) -> str:
    cleaned = INVALID_FILENAME_PATTERN.sub("_", name).replace("..", "")
    cleaned = cleaned.strip(" ._")
    return cleaned or "untitled"


class QueryResultWriter:
    def __init__(self, results_root: Path, clock: Callable[[], str]) -> None:
        self._results_root = results_root
        self._clock = clock

    def create_bundle(
        self,
        query_name: str,
        full_text_results: list[FullTextSearchResult],
        vector_results: list[VectorFileSearchResult],
    ) -> QueryResultBundle:
        bundle_dir = self._results_root / f"{self._clock()}-{safe_path_name(query_name)}"
        bundle_dir.mkdir(parents=True, exist_ok=False)

        full_text_path = bundle_dir / "full_text_results.json"
        vector_path = bundle_dir / "vector_results.json"
        _write_json(full_text_path, [result.to_dict() for result in full_text_results])
        _write_json(vector_path, [result.to_dict() for result in vector_results])

        return QueryResultBundle(
            path=bundle_dir,
            full_text_results_path=full_text_path,
            vector_results_path=vector_path,
            full_text_results=full_text_results,
            vector_results=vector_results,
        )


def _write_json(path: Path, data: object) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
