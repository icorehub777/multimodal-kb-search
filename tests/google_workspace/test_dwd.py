"""
Google Workspace Domain-Wide Delegation 串接測試（無 JSON 金鑰）。

執行前請完成 README.md 中的環境設定，並在 .env 填入 GOOGLE_DWD_SUBJECT_EMAIL。

用法：
    python test_dwd.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build

# 從本目錄載入 .env
load_dotenv(Path(__file__).resolve().parent / ".env")

from dwd_auth import credentials_from_dwd_token, get_dwd_token, get_subject_email  # noqa: E402


def main() -> int:
    subject = get_subject_email()
    print(f"正在以 {subject} 的身分取得授權...")

    try:
        access_token = get_dwd_token()
        creds = credentials_from_dwd_token(access_token)
        drive_service = build("drive", "v3", credentials=creds)

        print("成功連線！正在讀取該帳號的前 5 個檔案...")
        results = (
            drive_service.files()
            .list(pageSize=5, fields="nextPageToken, files(id, name)")
            .execute()
        )
        items = results.get("files", [])

        if not items:
            print("該帳號的雲端硬碟中沒有找到檔案。")
        else:
            for item in items:
                print(f"檔名: {item['name']} (ID: {item['id']})")

        return 0
    except Exception as exc:
        print(f"發生錯誤：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
