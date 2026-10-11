from __future__ import annotations

import base64
import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kbsearch_cli.config import resolve_workspace_tasks_root
from kbsearch_cli.errors import QueryInputError
from kbsearch_cli.paths import require_scoped_path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


@dataclass(frozen=True)
class JsonState:
    ok: bool
    data: Any
    error: str = ""


@dataclass(frozen=True)
class QueryResult:
    task_name: str
    query_name: str
    path: Path


def viewer_tasks_dir() -> Path:
    return resolve_workspace_tasks_root()


def discover_query_results(tasks_dir: Path | None = None) -> list[QueryResult]:
    if tasks_dir is None:
        tasks_dir = viewer_tasks_dir()
    if not tasks_dir.exists():
        return []

    results: list[QueryResult] = []
    tasks_dir = tasks_dir.resolve()
    task_dirs = sorted((p for p in tasks_dir.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True)
    for task_dir in task_dirs:
        require_scoped_path(task_dir, tasks_dir)
        query_results_dir = task_dir / "query_results"
        require_scoped_path(query_results_dir, task_dir)
        if not query_results_dir.exists():
            continue
        query_dirs = sorted((p for p in query_results_dir.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True)
        for query_dir in query_dirs:
            require_scoped_path(query_dir, query_results_dir)
            results.append(QueryResult(task_name=task_dir.name, query_name=query_dir.name, path=query_dir))
    return results


def read_json(path: Path, default: Any, *, boundary: Path) -> JsonState:
    try:
        require_scoped_path(path, boundary)
        if not path.exists():
            return JsonState(ok=True, data=default)
        return JsonState(ok=True, data=json.loads(path.read_text(encoding="utf-8")))
    except Exception as exc:
        return JsonState(ok=False, data=default, error=f"{path.name}: {exc}")


def normalize_results(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        return []

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "index": index,
                "google_file_id": str(item.get("google_file_id") or ""),
                "name": item.get("source_name") or item.get("name") or item.get("google_file_id") or f"未命名檔案 {index + 1}",
                "location": item.get("source_location") or "",
                "url": item.get("source_url") or item.get("web_url") or "",
                "score": item.get("score"),
                "pages": normalize_pages(item.get("pages")),
            }
        )
    return normalized


def normalize_pages(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        return []

    pages: list[dict[str, Any]] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        page_number = item.get("page_number") or item.get("page") or index + 1
        try:
            page_number = int(page_number)
        except (TypeError, ValueError):
            continue
        pages.append(
            {
                "page_number": page_number,
                "score": item.get("score"),
                "keyword": item.get("keyword") or item.get("query") or "",
            }
        )
    return pages


def normalize_downloaded_files(data: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(data, list):
        return {}

    downloaded_files: dict[str, dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        google_file_id = str(item.get("google_file_id") or "")
        if not google_file_id:
            continue
        downloaded_files[google_file_id] = item
    return downloaded_files


def resolve_recorded_path(query_dir: Path, raw_path: Any) -> Path | None:
    if not raw_path:
        return None
    path = Path(str(raw_path))
    candidate = path if path.is_absolute() else query_dir / path
    candidate = require_scoped_path(candidate, query_dir)
    return candidate if candidate.exists() else None


def find_document_dir(
    query_dir: Path,
    result: dict[str, Any],
    downloaded_files: dict[str, dict[str, Any]],
) -> Path | None:
    downloaded_file = downloaded_files.get(str(result.get("google_file_id") or ""))
    if downloaded_file is None:
        return None
    directory = resolve_recorded_path(query_dir, downloaded_file.get("directory"))
    if directory is not None and (directory.parent != query_dir.resolve() or not directory.is_dir()):
        raise QueryInputError(f"Document directory must be a direct child of the query: {directory}")
    return directory


def find_page_image(
    query_dir: Path,
    result: dict[str, Any],
    page_number: int,
    downloaded_files: dict[str, dict[str, Any]],
) -> Path | None:
    downloaded_file = downloaded_files.get(str(result.get("google_file_id") or ""))
    if downloaded_file is None:
        return None

    document_dir = find_document_dir(query_dir, result, downloaded_files)
    if document_dir is None:
        return None
    pages_dir = require_scoped_path(document_dir / "pages", document_dir)
    for raw_page_path in downloaded_file.get("page_paths") or []:
        image_path = resolve_recorded_path(query_dir, raw_page_path)
        if image_path is not None:
            require_scoped_path(image_path, pages_dir)
        if image_path is not None and image_path.name in {f"{page_number:04d}.png", f"{page_number}.png"}:
            return image_path

    for file_name in (f"{page_number:04d}.png", f"{page_number}.png"):
        image_path = pages_dir / file_name
        require_scoped_path(image_path, document_dir)
        if image_path.exists():
            return image_path
    return None


def find_condition_images(query_dir: Path, plan: dict[str, Any]) -> list[Path]:
    image_paths = plan.get("image_paths")
    if not isinstance(image_paths, list):
        return []

    images: list[Path] = []
    for raw_path in image_paths:
        if not raw_path:
            continue
        path = Path(str(raw_path))
        task_dir = query_dir.parent.parent
        candidate = path if path.is_absolute() else task_dir / path
        candidate = require_scoped_path(candidate, task_dir)
        if candidate.parent != task_dir.resolve():
            raise QueryInputError(f"Query image must be directly within the task directory: {candidate}")
        if candidate.is_file() and candidate.suffix.lower() in IMAGE_EXTENSIONS:
            images.append(candidate)
    return images


def format_score(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return ""


def image_to_data_uri(path: Path, *, boundary: Path) -> str:
    require_scoped_path(path, boundary)
    mime_type = "image/png"
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        mime_type = "image/jpeg"
    elif suffix == ".webp":
        mime_type = "image/webp"
    elif suffix == ".gif":
        mime_type = "image/gif"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def inject_styles() -> None:
    import streamlit as st

    st.markdown(
        """
        <style>
          .block-container {
            padding-top: 3rem;
            max-width: 100%;
            overflow-x: hidden;
          }
          html,
          body,
          #root,
          div[data-testid="stApp"],
          div[data-testid="stAppViewContainer"],
          section[data-testid="stMain"] {
            scrollbar-gutter: stable;
          }
          html,
          body {
            height: auto !important;
            min-height: 100% !important;
            overflow-y: auto !important;
          }
          #root,
          #root > div,
          div[data-testid="stScreencast"],
          div[data-testid="stApp"],
          div[data-testid="stAppViewContainer"],
          div[data-testid="stAppViewContainer"] > div {
            height: auto !important;
            min-height: 100vh !important;
            overflow: visible !important;
          }
          div[data-testid="stApp"],
          div[data-testid="stAppViewContainer"] {
            position: static !important;
          }
          section[data-testid="stMain"] {
            height: auto !important;
            overflow: visible !important;
          }
          div[data-testid="stMainBlockContainer"] {
            height: auto !important;
            overflow-y: visible !important;
          }
          div[data-testid="stVerticalBlock"],
          div[data-testid="stHorizontalBlock"],
          div[data-testid="stLayoutWrapper"],
          div[data-testid="column"],
          div[data-testid="stTabs"],
          div[data-testid="stTabContent"],
          div[data-testid="stExpander"] {
            min-width: 0 !important;
            max-width: 100% !important;
          }
          div[data-testid="stVerticalBlock"],
          div[data-testid="stLayoutWrapper"] {
            width: 100% !important;
          }
          div[data-testid="stTabContent"] {
            width: 100% !important;
            overflow-x: hidden;
          }
          div[data-testid="stSelectbox"],
          div[data-testid="stSelectbox"] > div,
          div[data-testid="stSelectbox"] div[data-baseweb="select"] {
            width: 100% !important;
            min-width: 0 !important;
            max-width: 100% !important;
          }
          div[data-testid="stLayoutWrapper"]:has(div[data-testid="stSelectbox"]) {
            width: calc(100vw - 182px) !important;
            min-width: calc(100vw - 182px) !important;
            max-width: calc(100vw - 182px) !important;
          }
          div[data-testid="stLayoutWrapper"]:has(div[data-testid="stSelectbox"]) div[data-testid="stHorizontalBlock"] {
            width: 100% !important;
            overflow-x: hidden;
            overflow-y: visible !important;
          }
          @media (max-width: 900px) {
            div[data-testid="stLayoutWrapper"]:has(div[data-testid="stSelectbox"]) {
              width: 100% !important;
              min-width: 0 !important;
              max-width: 100% !important;
            }
          }
          div[data-testid="stExpander"] details summary p {
            font-size: 0.95rem !important;
            font-weight: 700 !important;
          }
          div[data-testid="stExpanderDetails"] {
            padding: 22px !important;
            min-width: 0 !important;
            max-width: 100% !important;
            overflow: visible !important;
          }
          label[data-testid="stWidgetLabel"] p {
            font-size: 0.95rem !important;
            font-weight: 700 !important;
          }
          div[role="tab"] p {
            font-size: 0.95rem !important;
            font-weight: 700 !important;
          }
          .condition-lines {
            font-size: 0.9rem !important;
            line-height: 1.6;
            color: inherit;
            padding: 0;
          }
          .condition-lines div {
            margin: 0 0 0.38rem;
            overflow-wrap: anywhere;
          }
          .condition-lines div:last-child {
            margin-bottom: 0;
          }
          div[data-testid="stExpanderDetails"] div[data-testid="stMarkdownContainer"]:has(.condition-lines) {
            margin-bottom: 0 !important;
          }
          .condition-images {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 4px 0 8px;
          }
          .condition-images img {
            width: 120px;
            max-height: 120px;
            object-fit: contain;
            border: 1px solid #d8dde6;
            border-radius: 6px;
            background: #fff;
          }
          .drive-path {
            margin: 0 0 22px;
            overflow-wrap: anywhere;
            font-size: 0.88rem;
          }
          .empty-result {
            margin: 14px 0;
            text-align: center;
            color: rgba(250, 250, 250, 0.65);
            font-size: 1rem;
          }
          .muted-centered-message {
            margin: 10px 0;
            text-align: center;
            color: rgba(250, 250, 250, 0.65);
            font-size: 1rem;
          }
          .page-thumb-card {
            display: block;
            width: 100%;
            margin: 0 0 18px;
            padding: 10px;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            background: #fff;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.12);
            cursor: pointer;
          }
          .page-thumb-card:focus {
            outline: 2px solid #2563eb;
            outline-offset: 2px;
          }
          .page-thumb-card img {
            display: block;
            width: 100%;
            max-height: 340px;
            object-fit: contain;
            background: #fff;
          }
          .page-thumb-caption {
            margin-top: 8px;
            text-align: center;
            color: #111827;
            font-size: 0.9rem;
            line-height: 1.45;
          }
          .kbsearch-image-modal {
            position: fixed;
            inset: 0;
            z-index: 2147483647;
            display: none;
            align-items: center;
            justify-content: center;
            padding: 16px;
            background: rgba(0, 0, 0, 0.72);
          }
          .kbsearch-image-modal.is-open {
            display: flex;
          }
          .kbsearch-image-modal__panel {
            position: relative;
            max-width: min(98vw, 1800px);
            max-height: 96vh;
          }
          .kbsearch-image-modal__image {
            display: block;
            max-width: 98vw;
            max-height: 96vh;
            object-fit: contain;
            background: #fff;
            border: 1px solid rgba(255, 255, 255, 0.45);
            border-radius: 4px;
          }
          .kbsearch-image-modal__close {
            position: absolute;
            top: 10px;
            right: 10px;
            width: 36px;
            height: 36px;
            border: 0;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.9);
            color: #111827;
            font-size: 24px;
            line-height: 36px;
            cursor: pointer;
            box-shadow: 0 1px 6px rgba(0, 0, 0, 0.28);
          }
          button[title="View fullscreen"],
          button[aria-label="Fullscreen"] {
            display: none !important;
          }
          @media (prefers-color-scheme: light) {
            .empty-result {
              color: rgba(49, 51, 63, 0.65);
            }
            .muted-centered-message {
              color: rgba(49, 51, 63, 0.65);
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_image_modal_script() -> None:
    import streamlit as st

    st.iframe(
        """
        <script>
          (() => {
            const doc = window.parent.document;

            const ensureModal = () => {
              let modal = doc.getElementById("kbsearch-image-modal");
              if (modal) {
                return modal;
              }

              modal = doc.createElement("div");
              modal.id = "kbsearch-image-modal";
              modal.className = "kbsearch-image-modal";
              modal.innerHTML = `
                <div class="kbsearch-image-modal__panel">
                  <button type="button" class="kbsearch-image-modal__close" aria-label="關閉圖片">×</button>
                  <img class="kbsearch-image-modal__image" alt="">
                </div>
              `;
              doc.body.appendChild(modal);

              const close = () => modal.classList.remove("is-open");
              modal.addEventListener("click", (event) => {
                if (event.target === modal) {
                  close();
                }
              });
              modal.querySelector(".kbsearch-image-modal__close").addEventListener("click", close);
              doc.addEventListener("keydown", (event) => {
                if (event.key === "Escape") {
                  close();
                }
              });
              return modal;
            };

            const openModal = (trigger) => {
              const modal = ensureModal();
              const image = modal.querySelector(".kbsearch-image-modal__image");
              image.src = trigger.dataset.kbsearchFullSrc || "";
              image.alt = trigger.dataset.kbsearchTitle || "";
              modal.classList.add("is-open");
            };

            const bindTriggers = () => {
              doc.querySelectorAll(".kbsearch-image-trigger:not([data-kbsearch-bound])").forEach((trigger) => {
                trigger.dataset.kbsearchBound = "true";
                trigger.addEventListener("click", () => openModal(trigger));
                trigger.addEventListener("keydown", (event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openModal(trigger);
                  }
                });
              });
            };

            bindTriggers();
            if (!window.parent.__kbsearchImageModalObserver) {
              window.parent.__kbsearchImageModalObserver = new MutationObserver(bindTriggers);
              window.parent.__kbsearchImageModalObserver.observe(doc.body, {
                childList: true,
                subtree: true,
              });
            }
          })();
        </script>
        """,
        height=1,
        tab_index=-1,
    )


def render_conditions(query: QueryResult, plan_state: JsonState) -> None:
    import streamlit as st

    if not plan_state.ok:
        st.warning(plan_state.error)
        return

    plan = plan_state.data if isinstance(plan_state.data, dict) else {}
    image_paths = find_condition_images(query.path, plan)
    image_html = ""
    if image_paths:
        image_tags = "".join(
            f'<img src="{image_to_data_uri(path, boundary=query.path.parent.parent)}" alt="{html.escape(path.name)}">' for path in image_paths
        )
        image_html = f'<div class="condition-images">{image_tags}</div>'

    with st.expander("**搜尋條件**", expanded=True):
        st.markdown(
            f"""
            <div class="condition-lines">
              <div><strong>相似度搜尋：</strong>{html.escape(str(plan.get("vector_query") or "未設定"))}</div>
              <div><strong>關鍵字搜尋：</strong>{html.escape(str(plan.get("drive_query") or "未設定"))}</div>
              <div><strong>圖片條件：</strong>{image_html or "未設定"}</div>
              <div><strong>筆數上限：</strong>{html.escape(str(plan.get("limit") if plan.get("limit") is not None else "未設定"))}</div>
              <div><strong>最低相似度分數：</strong>{html.escape(str(plan.get("min_score") if plan.get("min_score") is not None else "未設定"))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def result_summary(results: list[dict[str, Any]]) -> str:
    page_count = sum(len(result["pages"]) for result in results)
    return f"總檔案：{len(results)}；總結果數量：{page_count or len(results)}；命中頁面：{page_count}"


def inject_tab_tooltips(vector_summary: str, keyword_summary: str) -> None:
    import streamlit as st

    payload = json.dumps(
        {
            "相似度搜尋清單": vector_summary,
            "關鍵字搜尋清單": keyword_summary,
        },
        ensure_ascii=False,
    )
    st.iframe(
        f"""
        <script>
          const tooltips = {payload};
          const applyTooltips = () => {{
            const tabs = window.parent.document.querySelectorAll('[role="tab"]');
            tabs.forEach((tab) => {{
              const label = tab.innerText.trim();
              const normalized = label.replaceAll('*', '').trim();
              if (tooltips[normalized]) {{
                tab.setAttribute('title', tooltips[normalized]);
              }}
            }});
          }};
          applyTooltips();
          setTimeout(applyTooltips, 500);
        </script>
        """,
        height=1,
        tab_index=-1,
    )


def render_drive_path(st: Any, result: dict[str, Any]) -> None:
    location = str(result.get("location") or "")
    url = str(result.get("url") or "")
    display_path = location or url
    if not display_path:
        return

    if url:
        st.markdown(
            f'<div class="drive-path"><a href="{html.escape(url)}" target="_blank" rel="noreferrer">'
            f'{html.escape(display_path)}</a></div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(f'<div class="drive-path">{html.escape(display_path)}</div>', unsafe_allow_html=True)


def query_param_value(st: Any, name: str) -> str:
    value = st.query_params.get(name, "")
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


def run_app() -> None:
    import streamlit as st

    st.set_page_config(page_title="知識庫搜尋結果檢視", layout="wide")
    inject_styles()
    inject_image_modal_script()

    try:
        query_results = discover_query_results()
    except QueryInputError as exc:
        st.error(str(exc))
        return
    if not query_results:
        st.info(f"找不到查詢結果資料夾：{viewer_tasks_dir()}")
        return

    tasks = sorted({result.task_name for result in query_results}, reverse=True)
    requested_task = query_param_value(st, "task")
    task_index = tasks.index(requested_task) if requested_task in tasks else 0
    selector_cols = st.columns(2)
    with selector_cols[0]:
        selected_task = st.selectbox("**搜尋任務**", tasks, index=task_index)
    task_queries = [result for result in query_results if result.task_name == selected_task]
    query_names = [result.query_name for result in task_queries]
    requested_query = query_param_value(st, "query")
    query_index = query_names.index(requested_query) if requested_query in query_names else 0
    with selector_cols[1]:
        selected_query_name = st.selectbox("**搜尋結果**", query_names, index=query_index)
    selected_query = next(result for result in task_queries if result.query_name == selected_query_name)
    if query_param_value(st, "task") != selected_task or query_param_value(st, "query") != selected_query_name:
        st.query_params["task"] = selected_task
        st.query_params["query"] = selected_query_name

    plan_state = read_json(selected_query.path / "query_plan.json", {}, boundary=selected_query.path)
    vector_state = read_json(selected_query.path / "vector_results.json", [], boundary=selected_query.path)
    keyword_state = read_json(selected_query.path / "full_text_results.json", [], boundary=selected_query.path)
    downloaded_files_state = read_json(selected_query.path / "downloaded_files.json", [], boundary=selected_query.path)
    vector_results = normalize_results(vector_state.data) if vector_state.ok else []
    keyword_results = normalize_results(keyword_state.data) if keyword_state.ok else []
    downloaded_files = normalize_downloaded_files(downloaded_files_state.data) if downloaded_files_state.ok else {}
    if not downloaded_files_state.ok:
        st.error(downloaded_files_state.error)

    try:
        render_conditions(selected_query, plan_state)
    except QueryInputError as exc:
        st.error(str(exc))

    tab_vector, tab_keyword = st.tabs(["**相似度搜尋清單**", "**關鍵字搜尋清單**"])
    inject_tab_tooltips(result_summary(vector_results), result_summary(keyword_results))
    with tab_vector:
        render_result_tab(st, selected_query, vector_state, vector_results, downloaded_files)
    with tab_keyword:
        render_result_tab(st, selected_query, keyword_state, keyword_results, downloaded_files)


def render_result_tab(
    st: Any,
    query: QueryResult,
    result_state: JsonState,
    results: list[dict[str, Any]],
    downloaded_files: dict[str, dict[str, Any]],
) -> None:
    if not result_state.ok:
        st.error(result_state.error)

    if not results:
        st.markdown('<div class="empty-result">無資料</div>', unsafe_allow_html=True)
        return

    for result in results:
        with st.expander(str(result["name"]), expanded=True):
            render_drive_path(st, result)
            pages = result["pages"]
            if not pages:
                st.markdown(
                    '<div class="muted-centered-message">此檔案沒有命中頁面資料。</div>',
                    unsafe_allow_html=True,
                )
                continue

            columns = st.columns(4)
            for index, page in enumerate(pages):
                try:
                    image_path = find_page_image(query.path, result, page["page_number"], downloaded_files)
                except QueryInputError as exc:
                    st.error(str(exc))
                    continue
                with columns[index % 4]:
                    if image_path is None:
                        st.markdown(
                            f'<div class="muted-centered-message">{format_page_caption(page)}<br>找不到縮圖</div>',
                            unsafe_allow_html=True,
                        )
                        continue

                    try:
                        render_page_thumbnail(st, image_path, page, boundary=query.path)
                    except QueryInputError as exc:
                        st.error(str(exc))


def format_page_caption(page: dict[str, Any]) -> str:
    lines = [f"第 {page['page_number']} 頁"]
    page_score = format_score(page["score"])
    if page_score:
        lines.append(f"相似度分數：{page_score}")
    if page["keyword"]:
        lines.append(f"命中關鍵字：{page['keyword']}")
    return "<br>".join(html.escape(line) for line in lines)


def page_caption_text(page: dict[str, Any]) -> str:
    lines = [f"第 {page['page_number']} 頁"]
    page_score = format_score(page["score"])
    if page_score:
        lines.append(f"相似度分數：{page_score}")
    if page["keyword"]:
        lines.append(f"命中關鍵字：{page['keyword']}")
    return " / ".join(lines)


def render_page_thumbnail(st: Any, image_path: Path, page: dict[str, Any], *, boundary: Path) -> None:
    image_uri = image_to_data_uri(image_path, boundary=boundary)
    title = page_caption_text(page)
    st.markdown(
        f"""
        <div
          class="page-thumb-card kbsearch-image-trigger"
          role="button"
          tabindex="0"
          aria-label="{html.escape(title, quote=True)}"
          data-kbsearch-full-src="{html.escape(image_uri, quote=True)}"
          data-kbsearch-title="{html.escape(title, quote=True)}"
        >
          <img src="{html.escape(image_uri, quote=True)}" alt="{html.escape(title, quote=True)}">
          <div class="page-thumb-caption">{format_page_caption(page)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    run_app()
