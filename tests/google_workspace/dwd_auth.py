"""以 IAM Credentials API 動態簽署 JWT，取得 Domain-Wide Delegation Access Token（無 JSON 金鑰）。"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import google.auth
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

DEFAULT_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
TOKEN_AUDIENCE = "https://oauth2.googleapis.com/token"
SIGN_JWT_URL_TEMPLATE = (
    "https://iamcredentials.googleapis.com/v1/projects/-"
    "/serviceAccounts/{service_account_email}:signJwt"
)


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(
            f"環境變數 {name} 未設定。請複製 .env.example 為 .env 並填入正確值。"
        )
    return value


def get_service_account_email() -> str:
    return _require_env("GOOGLE_SERVICE_ACCOUNT_EMAIL")


def get_subject_email() -> str:
    return _require_env("GOOGLE_DWD_SUBJECT_EMAIL")


def get_drive_scope() -> str:
    return os.environ.get("GOOGLE_DRIVE_SCOPE", DEFAULT_DRIVE_SCOPE).strip()


def get_dwd_token(
    *,
    service_account_email: str | None = None,
    subject_email: str | None = None,
    scope: str | None = None,
) -> str:
    """
    透過 Application Default Credentials + IAM signJwt 取得 DWD Access Token。

    前置條件：
    - 已執行 `gcloud auth application-default login`（具備 Service Account Token Creator）
    - GCP 已啟用 IAM Service Account Credentials API
    - Workspace 管理員已為服務帳戶設定 Domain-Wide Delegation 與對應 scope
    """
    sa_email = service_account_email or get_service_account_email()
    sub_email = subject_email or get_subject_email()
    oauth_scope = scope or get_drive_scope()

    credentials, _project = google.auth.default()
    credentials.refresh(Request())

    iat = int(time.time())
    payload: dict[str, Any] = {
        "iss": sa_email,
        "sub": sub_email,
        "aud": TOKEN_AUDIENCE,
        "iat": iat,
        "exp": iat + 3600,
        "scope": oauth_scope,
    }

    sign_url = SIGN_JWT_URL_TEMPLATE.format(service_account_email=sa_email)
    sign_response = requests.post(
        sign_url,
        headers={
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json",
        },
        json={"payload": json.dumps(payload)},
        timeout=30,
    )
    sign_response.raise_for_status()
    signed_jwt = sign_response.json()["signedJwt"]

    token_response = requests.post(
        TOKEN_AUDIENCE,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": signed_jwt,
        },
        timeout=30,
    )
    token_response.raise_for_status()
    return token_response.json()["access_token"]


def credentials_from_dwd_token(access_token: str) -> Credentials:
    return Credentials(token=access_token)
