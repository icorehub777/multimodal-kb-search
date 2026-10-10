from __future__ import annotations

import json
import re
from pathlib import Path

from kbsearch_cli.errors import QueryCliError, QueryInputError
from kbsearch_cli.paths import require_scoped_path
from kbsearch_cli.models import (
    DownloadedFileResult,
    DownloadFailureResult,
    FullTextSearchResult,
    QueryResultBundle,
    QueryWarningResult,
    VectorFileSearchResult,
)


INVALID_FILENAME_PATTERN = re.compile(r'[<>:"/\\\\|?*]+')


def validate_path_name(name: str, option: str) -> None:
    reserved = re.fullmatch(
        r"CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³]", name.split(".")[0], re.IGNORECASE
    )
    if (
        not name
        or name != name.strip()
        or name in (".", "..")
        or name.endswith(".")
        or INVALID_FILENAME_PATTERN.search(name)
        or any(ord(char) < 32 for char in name)
        or reserved
    ):
        raise QueryInputError(f"{option} must be a valid single file or directory name: {name!r}")


def _resolve_tasks_root(tasks_root: Path) -> Path:
    root = tasks_root.resolve()
    if not root.is_relative_to(tasks_root.parent.resolve()):
        raise QueryInputError(f"Task root must remain within the workspace: {tasks_root}")
    require_scoped_path(tasks_root, tasks_root.parent)
    return root


def resolve_query_output_directory(tasks_root: Path, task_name: str, query_name: str) -> Path:
    validate_path_name(task_name, "--task-name")
    validate_path_name(query_name, "--query-name")
    try:
        root = _resolve_tasks_root(tasks_root)
        output = root / task_name / "query_results" / query_name
        if not output.resolve().is_relative_to(root):
            raise QueryInputError(f"Query output directory must remain within the task root: {output}")
        require_scoped_path(output, root)
        for parent in (root, output.parent.parent, output.parent):
            if parent.exists() and not parent.is_dir():
                raise QueryInputError(f"Task directory path is not a directory: {parent}")
        if output.exists() or output.is_symlink():
            raise QueryInputError(f"Query output directory already exists: {output}")
        return output
    except QueryInputError:
        raise
    except (OSError, RuntimeError) as exc:
        raise QueryInputError(f"Cannot resolve query output under the task root: {tasks_root}") from exc


def resolve_query_image_paths(tasks_root: Path, task_name: str, image_names: list[str]) -> list[Path]:
    validate_path_name(task_name, "--task-name")
    for name in image_names:
        validate_path_name(name, "--image")
    if not image_names:
        return []
    try:
        root = _resolve_tasks_root(tasks_root)
        task = (root / task_name).resolve()
        if not task.is_relative_to(root):
            raise QueryInputError(f"Task directory must remain within the task root: {task}")
        require_scoped_path(root / task_name, root)
        images = []
        for name in image_names:
            image = (task / name).resolve()
            if not image.is_relative_to(task):
                raise QueryInputError(f"--image must remain within the task directory: {name!r}")
            require_scoped_path(task / name, task)
            if not image.is_file():
                raise QueryInputError(f"Query image not found: {image}")
            images.append(image)
        return images
    except QueryInputError:
        raise
    except (OSError, RuntimeError) as exc:
        raise QueryInputError(f"Cannot read query images in task directory: {tasks_root / task_name}") from exc


def resolve_render_paths(
    tasks_root: Path, task_name: str, query_name: str, document_name: str,
) -> tuple[Path, Path]:
    for name, option in ((task_name, "--task-name"), (query_name, "--query-name"),
                         (document_name, "--document-name")):
        validate_path_name(name, option)
    root = _resolve_tasks_root(tasks_root)
    document = require_scoped_path(root / task_name / "query_results" / query_name / document_name, root)
    pdf = require_scoped_path(document / "pdf" / "document.pdf", document)
    pages = require_scoped_path(document / "pages", document)
    if not pdf.is_file():
        raise QueryInputError(f"Search-result PDF not found: {pdf}")
    if pages.exists() and not pages.is_dir():
        raise QueryInputError(f"Page output is not a directory: {pages}")
    return pdf, pages


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
        downloaded_files_path = output_dir / "downloaded_files.json"
        download_failures_path = output_dir / "download_failures.json"
        warnings_path = output_dir / "warnings.json"
        _write_json(query_plan_path, query_plan)
        _write_json(full_text_path, [result.to_dict() for result in full_text_results])
        _write_json(vector_path, [result.to_dict() for result in vector_results])
        _write_json(downloaded_files_path, [])
        _write_json(download_failures_path, [])
        _write_json(warnings_path, [])

        return QueryResultBundle(
            path=output_dir,
            query_plan_path=query_plan_path,
            full_text_results_path=full_text_path,
            vector_results_path=vector_path,
            downloaded_files_path=downloaded_files_path,
            download_failures_path=download_failures_path,
            warnings_path=warnings_path,
            full_text_results=full_text_results,
            vector_results=vector_results,
        )

    def write_downloaded_files(
        self,
        bundle: QueryResultBundle,
        downloaded_files: list[DownloadedFileResult],
    ) -> None:
        _write_json(
            bundle.downloaded_files_path,
            [downloaded_file.to_dict() for downloaded_file in downloaded_files],
        )

    def write_download_failures(
        self,
        bundle: QueryResultBundle,
        failures: list[DownloadFailureResult],
    ) -> None:
        _write_json(
            bundle.download_failures_path,
            [failure.to_dict() for failure in failures],
        )

    def write_full_text_results(
        self,
        bundle: QueryResultBundle,
        full_text_results: list[FullTextSearchResult],
    ) -> None:
        _write_json(
            bundle.full_text_results_path,
            [result.to_dict() for result in full_text_results],
        )

    def write_warnings(
        self,
        bundle: QueryResultBundle,
        warnings: list[QueryWarningResult],
    ) -> None:
        _write_json(
            bundle.warnings_path,
            [warning.to_dict() for warning in warnings],
        )


def reserve_output_directory(output_dir: Path) -> None:
    try:
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise QueryInputError(f"Query output directory already exists: {output_dir}") from exc
    except OSError as exc:
        raise QueryCliError(f"Query output directory cannot be created: {output_dir}") from exc


def _write_json(path: Path, data: object) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
