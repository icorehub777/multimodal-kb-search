"""列出目前身分可存取的所有雲端硬碟與檔案/資料夾樹狀結構。"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build

_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / ".env")

from dwd_auth import credentials_from_dwd_token, get_dwd_token, get_subject_email  # noqa: E402

FOLDER_MIME = "application/vnd.google-apps.folder"
PAGE_SIZE = 1000


def _paginate_list(request_builder):
    items: list[dict] = []
    page_token = None
    while True:
        req = request_builder(page_token)
        resp = req.execute()
        items.extend(resp.get("files", resp.get("drives", [])))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return items


def list_shared_drives(drive) -> list[dict]:
    return _paginate_list(
        lambda token: drive.drives().list(
            pageSize=100,
            pageToken=token,
            fields="nextPageToken,drives(id,name)",
        )
    )


def list_files_in_drive(drive, drive_id: str | None, drive_label: str) -> list[dict]:
    """drive_id=None 表示「我的雲端硬碟」。"""
    q = "trashed = false"
    kwargs: dict = {
        "q": q,
        "pageSize": PAGE_SIZE,
        "fields": "nextPageToken,files(id,name,mimeType,parents)",
        "supportsAllDrives": True,
        "includeItemsFromAllDrives": True,
    }
    if drive_id:
        kwargs["corpora"] = "drive"
        kwargs["driveId"] = drive_id
    else:
        kwargs["corpora"] = "user"

    files = _paginate_list(
        lambda token: drive.files().list(pageToken=token, **kwargs)
    )
    return files


def build_tree(files: list[dict], root_parent: str) -> dict:
    """parent_id -> children；root 為 root_parent 或 parents 不在本 drive 的節點。"""
    by_id = {f["id"]: f for f in files}
    children: dict[str, list[dict]] = defaultdict(list)
    roots: list[dict] = []

    for f in files:
        parents = f.get("parents") or []
        parent = parents[0] if parents else None
        if parent and parent in by_id:
            children[parent].append(f)
        else:
            roots.append(f)

    return {"roots": roots, "children": children, "by_id": by_id}


def print_tree(
    node: dict,
    children_map: dict[str, list[dict]],
    prefix: str = "",
    is_last: bool = True,
) -> None:
    connector = "└── " if is_last else "├── "
    kind = "[資料夾]" if node.get("mimeType") == FOLDER_MIME else "[檔案]"
    print(f"{prefix}{connector}{kind} {node['name']}  (id={node['id']})")
    child_prefix = prefix + ("    " if is_last else "│   ")
    kids = sorted(
        children_map.get(node["id"], []),
        key=lambda x: (x.get("mimeType") != FOLDER_MIME, x.get("name", "").lower()),
    )
    for i, child in enumerate(kids):
        print_tree(child, children_map, child_prefix, i == len(kids) - 1)


def print_drive_section(title: str, drive_id: str | None, files: list[dict]) -> None:
    folders = sum(1 for f in files if f.get("mimeType") == FOLDER_MIME)
    docs = len(files) - folders
    id_part = f" (driveId={drive_id})" if drive_id else " (我的雲端硬碟)"
    print(f"\n{'=' * 72}")
    print(f"{title}{id_part}")
    print(f"共 {len(files)} 項（資料夾 {folders}、檔案 {docs}）")
    print("=" * 72)

    if not files:
        print("（空）")
        return

    tree = build_tree(files, "root")
    roots = sorted(
        tree["roots"],
        key=lambda x: (x.get("mimeType") != FOLDER_MIME, x.get("name", "").lower()),
    )
    for i, root in enumerate(roots):
        print_tree(root, tree["children"], "", i == len(roots) - 1)


def main() -> int:
    subject = get_subject_email()
    print(f"身分: {subject}\n")

    creds = credentials_from_dwd_token(get_dwd_token())
    drive = build("drive", "v3", credentials=creds)

    shared = list_shared_drives(drive)
    print(f"可存取的共用雲端硬碟: {len(shared)} 個")
    for d in shared:
        print(f"  - {d['name']}  (id={d['id']})")

    my_files = list_files_in_drive(drive, None, "我的雲端硬碟")
    print_drive_section("我的雲端硬碟", None, my_files)

    for d in shared:
        files = list_files_in_drive(drive, d["id"], d["name"])
        print_drive_section(d["name"], d["id"], files)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
