"""單一關鍵字 Drive 搜尋（可傳入參數，預設：推車輪組）。"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build

_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / ".env")

from dwd_auth import credentials_from_dwd_token, get_dwd_token, get_subject_email  # noqa: E402
from drive_helpers import escape_query_term  # noqa: E402


def main() -> int:
    term = sys.argv[1] if len(sys.argv) > 1 else "推車輪組"
    safe = escape_query_term(term)
    base = "trashed = false"

    drive = build("drive", "v3", credentials=credentials_from_dwd_token(get_dwd_token()))
    print(f"身分: {get_subject_email()}")
    print(f"關鍵字: {term}\n")

    queries = [
        ("檔名 name contains", f"{base} and name contains '{safe}'"),
        ("全文 fullText contains", f"{base} and fullText contains '{safe}'"),
        ("綜合 name OR fullText", f"{base} and (name contains '{safe}' or fullText contains '{safe}')"),
    ]
    scopes = [
        ("我的雲端硬碟", {"corpora": "user"}),
        (
            "全部可存取 (allDrives)",
            {
                "corpora": "allDrives",
                "includeItemsFromAllDrives": True,
                "supportsAllDrives": True,
            },
        ),
    ]

    all_hits: dict[str, dict] = {}
    for label, q in queries:
        print(f"--- {label} ---")
        print(f"q = {q}")
        for scope_label, scope_kwargs in scopes:
            resp = (
                drive.files()
                .list(
                    q=q,
                    pageSize=50,
                    fields="files(id,name,mimeType,webViewLink)",
                    **scope_kwargs,
                )
                .execute()
            )
            files = resp.get("files", [])
            print(f"  [{scope_label}] {len(files)} 筆")
            for f in files:
                all_hits[f["id"]] = f
                print(f"    - {f['name']}")
                print(f"      mimeType={f['mimeType']}")
                print(f"      id={f['id']}")
                print(f"      link={f.get('webViewLink', '')}")
        print()

    print(f"三種查詢去重後合計: {len(all_hits)} 筆")
    return 0 if all_hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
