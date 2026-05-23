"""
模擬使用者查詢路徑，驗證四種 Drive API 行為（關鍵字：推車輪組）。

1. files.list（q）— 檔名 / 全文 / description(metadata) 搜尋
2. files.get — 讀取 metadata、確認可存取
3. files.get（alt=media）— 下載二進位原始檔
4. files.export — 匯出 Google 原生檔為 PDF

用法：
    python test_drive_four_behaviors.py

產物寫入 .output/（已 gitignore）
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / ".env")

from dwd_auth import credentials_from_dwd_token, get_dwd_token, get_subject_email  # noqa: E402
from drive_helpers import (  # noqa: E402
    EXPORT_TARGET_PDF,
    FILE_METADATA_FIELDS,
    escape_query_term,
    is_google_native,
)

SEARCH_KEYWORD = "推車輪組"
OUTPUT_DIR = _ROOT / ".output"


def _build_drive():
    creds = credentials_from_dwd_token(get_dwd_token())
    return build("drive", "v3", credentials=creds)


def _list_search(drive, label: str, query: str, page_size: int = 5) -> list[dict]:
    print(f"\n--- [files.list] {label} ---")
    print(f"q = {query}")
    result = (
        drive.files()
        .list(
            q=query,
            pageSize=page_size,
            fields="files(id,name,mimeType,webViewLink)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = result.get("files", [])
    if not files:
        print("（無命中）")
    else:
        for f in files:
            print(f"  - {f['name']} | {f['mimeType']} | id={f['id']}")
    return files


def demo_search(drive, term: str) -> list[dict]:
    """
    三種 q 查詢模擬：
    - 檔名
    - 全文 (fullText，含內文與部分可索引欄位)
    - 綜合（檔名 OR 全文，模擬 Agent 關鍵字搜尋）

    註：Drive q 不支援 description contains；自訂 metadata 需 properties/appProperties。
    """
    safe = escape_query_term(term)
    base = "trashed = false"
    by_name = _list_search(drive, "檔名包含", f"{base} and name contains '{safe}'")
    by_fulltext = _list_search(
        drive, "全文包含 (fullText)", f"{base} and fullText contains '{safe}'"
    )
    by_combined = _list_search(
        drive,
        "綜合（檔名 OR 全文）",
        f"{base} and (name contains '{safe}' or fullText contains '{safe}')",
    )
    merged: dict[str, dict] = {}
    for item in by_name + by_fulltext + by_combined:
        merged[item["id"]] = item
    return list(merged.values())


def demo_get_metadata(drive, file_id: str) -> dict:
    print(f"\n--- [files.get] 讀取 metadata / 權限確認 ---")
    print(f"file_id = {file_id}")
    meta = (
        drive.files()
        .get(fileId=file_id, fields=FILE_METADATA_FIELDS, supportsAllDrives=True)
        .execute()
    )
    print(f"  檔名: {meta.get('name')}")
    print(f"  mimeType: {meta.get('mimeType')}")
    print(f"  webViewLink: {meta.get('webViewLink')}")
    print(f"  version: {meta.get('version')}")
    print(f"  modifiedTime: {meta.get('modifiedTime')}")
    print(f"  trashed: {meta.get('trashed')}")
    print("  => 能成功 get 即代表目前身分對該檔仍有讀取權限")
    return meta


def demo_download_media(drive, file_id: str, name: str, mime_type: str) -> Path:
    print(f"\n--- [files.get] alt=media 下載二進位檔 ---")
    print(f"file_id = {file_id} ({name})")
    if is_google_native(mime_type):
        raise ValueError("此檔為 Google 原生格式，應使用 files.export，不可 alt=media")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ext = {
        "application/pdf": ".pdf",
        "text/plain": ".txt",
        "text/markdown": ".md",
    }.get(mime_type, ".bin")
    dest = OUTPUT_DIR / f"download_{file_id}{ext}"

    request = drive.files().get_media(fileId=file_id, supportsAllDrives=True)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _status, done = downloader.next_chunk()

    dest.write_bytes(buffer.getvalue())
    print(f"  已寫入: {dest} ({len(buffer.getvalue())} bytes)")
    return dest


def demo_export_pdf(drive, file_id: str, name: str) -> Path:
    print(f"\n--- [files.export] Google 原生檔 → PDF ---")
    print(f"file_id = {file_id} ({name})")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUTPUT_DIR / f"export_{file_id}.pdf"

    data = (
        drive.files()
        .export(fileId=file_id, mimeType=EXPORT_TARGET_PDF)
        .execute()
    )
    dest.write_bytes(data)
    print(f"  已寫入: {dest} ({len(data)} bytes)")
    return dest


def _pick_download_target(files: list[dict]) -> dict | None:
    for f in files:
        if not is_google_native(f.get("mimeType", "")):
            return f
    return None


def _pick_export_target(files: list[dict]) -> dict | None:
    for f in files:
        if is_google_native(f.get("mimeType", "")):
            return f
    return None


def _fallback_native_file(drive) -> dict | None:
    """搜尋無 Google 原生檔時，從最近文件中取一筆。"""
    result = (
        drive.files()
        .list(
            q=(
                "trashed = false and ("
                "mimeType = 'application/vnd.google-apps.document' or "
                "mimeType = 'application/vnd.google-apps.spreadsheet' or "
                "mimeType = 'application/vnd.google-apps.presentation'"
                ")"
            ),
            pageSize=1,
            fields="files(id,name,mimeType)",
            orderBy="modifiedTime desc",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = result.get("files", [])
    return files[0] if files else None


def _fallback_binary_file(drive) -> dict | None:
    result = (
        drive.files()
        .list(
            q=(
                "trashed = false and ("
                "mimeType = 'application/pdf' or "
                "mimeType contains 'officedocument' or "
                "mimeType = 'text/plain'"
                ")"
            ),
            pageSize=1,
            fields="files(id,name,mimeType)",
            orderBy="modifiedTime desc",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = result.get("files", [])
    return files[0] if files else None


def main() -> int:
    subject = get_subject_email()
    print(f"身分: {subject}（DWD 模擬，驗證 API 行為）")
    print(f"搜尋關鍵字: {SEARCH_KEYWORD}")

    drive = _build_drive()
    hits = demo_search(drive, SEARCH_KEYWORD)

    probe_id: str | None = None
    if not hits:
        print("\n關鍵字三種搜尋皆無命中；metadata 改以 fallback 檔案驗證。")
        fallback = _fallback_binary_file(drive) or _fallback_native_file(drive)
        if fallback:
            probe_id = fallback["id"]
            demo_get_metadata(drive, probe_id)
    else:
        probe_id = hits[0]["id"]
        demo_get_metadata(drive, probe_id)

    download_target = _pick_download_target(hits) or _fallback_binary_file(drive)
    export_target = _pick_export_target(hits) or _fallback_native_file(drive)

    ok_download = False
    ok_export = False

    if download_target:
        try:
            meta = (
                drive.files()
                .get(
                    fileId=download_target["id"],
                    fields="mimeType",
                    supportsAllDrives=True,
                )
                .execute()
            )
            demo_download_media(
                drive,
                download_target["id"],
                download_target["name"],
                meta["mimeType"],
            )
            ok_download = True
        except HttpError as exc:
            print(f"  下載失敗: {exc}")
    else:
        print("\n[略過] 找不到可 files.get(alt=media) 的二進位檔")

    if export_target:
        try:
            demo_export_pdf(drive, export_target["id"], export_target["name"])
            ok_export = True
        except HttpError as exc:
            print(f"  匯出失敗: {exc}")
    else:
        print("\n[略過] 找不到可 files.export 的 Google 原生檔")

    # list 三種 q 語法皆可執行即算 PASS；關鍵字無命中另提示
    search_ok = True
    metadata_ok = probe_id is not None

    print("\n========== 摘要 ==========")
    print(f"  files.list 搜尋: PASS（關鍵字命中 {len(hits)} 筆）")
    if not hits:
        print("    提示: 「推車輪組」無命中，請確認 Drive 內是否有含此詞的檔案")
    print(f"  files.get metadata: {'PASS' if metadata_ok else 'FAIL'}")
    print(f"  files.get alt=media: {'PASS' if ok_download else 'FAIL'}")
    print(f"  files.export: {'PASS' if ok_export else 'FAIL'}")

    if not metadata_ok or not ok_download or not ok_export:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
