from __future__ import annotations

import json
import re
from pathlib import Path

from kbsearch_cli.errors import QueryCliError
from kbsearch_cli.models import FullTextSearchResult, QueryResultBundle, VectorFileSearchResult


INVALID_FILENAME_PATTERN = re.compile(r'[<>:"/\\\\|?*]+')


def safe_path_name(name: str) -> str:
    cleaned = INVALID_FILENAME_PATTERN.sub("_", name).replace("..", "")
    cleaned = cleaned.strip(" ._")
    return cleaned or "untitled"


class QueryResultWriter:
    def create_bundle(
        self,
        output_dir: Path,
        query_plan: dict[str, object],
        full_text_results: list[FullTextSearchResult],
        vector_results: list[VectorFileSearchResult],
    ) -> QueryResultBundle:
        query_plan_path = output_dir / "query_plan.json"
        full_text_path = output_dir / "full_text_results.json"
        vector_path = output_dir / "vector_results.json"
        _write_json(query_plan_path, query_plan)
        _write_json(full_text_path, [result.to_dict() for result in full_text_results])
        _write_json(vector_path, [result.to_dict() for result in vector_results])

        return QueryResultBundle(
            path=output_dir,
            query_plan_path=query_plan_path,
            full_text_results_path=full_text_path,
            vector_results_path=vector_path,
            full_text_results=full_text_results,
            vector_results=vector_results,
        )


def reserve_output_directory(output_dir: Path) -> None:
    try:
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise QueryCliError(f"Query output directory already exists: {output_dir}") from exc
    except OSError as exc:
        raise QueryCliError(f"Query output directory cannot be created: {output_dir}") from exc


def _write_json(path: Path, data: object) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
