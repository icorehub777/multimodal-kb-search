"""
pytest 串接測試：驗證 DWD + Drive API 可列出檔案。

未設定 GOOGLE_DWD_SUBJECT_EMAIL 時自動略過（適合 CI 或未設定本機環境時）。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv(Path(__file__).resolve().parent / ".env")

from dwd_auth import credentials_from_dwd_token, get_dwd_token  # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.environ.get("GOOGLE_DWD_SUBJECT_EMAIL", "").strip(),
    reason="未設定 GOOGLE_DWD_SUBJECT_EMAIL，略過 Google Workspace 串接測試",
)


def test_dwd_drive_list_returns_files_structure():
    """以 DWD 身分呼叫 Drive files.list，回傳結構應含 files 鍵。"""
    access_token = get_dwd_token()
    creds = credentials_from_dwd_token(access_token)
    drive_service = build("drive", "v3", credentials=creds)

    results = (
        drive_service.files()
        .list(pageSize=5, fields="nextPageToken, files(id, name)")
        .execute()
    )

    assert "files" in results
    assert isinstance(results["files"], list)
