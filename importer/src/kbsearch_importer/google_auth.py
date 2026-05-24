from __future__ import annotations

import json
import time
from typing import Any

import requests

from kbsearch_importer.errors import ExternalServiceError

DEFAULT_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
TOKEN_AUDIENCE = "https://oauth2.googleapis.com/token"
SIGN_JWT_URL_TEMPLATE = (
    "https://iamcredentials.googleapis.com/v1/projects/-"
    "/serviceAccounts/{service_account_email}:signJwt"
)


def get_dwd_access_token(
    service_account_email: str,
    subject_email: str,
    *,
    scope: str = DEFAULT_DRIVE_SCOPE,
) -> str:
    try:
        import google.auth
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise RuntimeError("google-auth is required for Google Workspace authentication.") from exc

    try:
        credentials, _project = google.auth.default()
        credentials.refresh(Request())
    except Exception as exc:
        raise ExternalServiceError(
            "Google Application Default Credentials refresh failed. "
            "Run `gcloud.cmd auth application-default login` and retry."
        ) from exc

    iat = int(time.time())
    payload: dict[str, Any] = {
        "iss": service_account_email,
        "sub": subject_email,
        "aud": TOKEN_AUDIENCE,
        "iat": iat,
        "exp": iat + 3600,
        "scope": scope,
    }

    try:
        sign_response = requests.post(
            SIGN_JWT_URL_TEMPLATE.format(service_account_email=service_account_email),
            headers={
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
            },
            json={"payload": json.dumps(payload)},
            timeout=30,
        )
        sign_response.raise_for_status()

        token_response = requests.post(
            TOKEN_AUDIENCE,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": sign_response.json()["signedJwt"],
            },
            timeout=30,
        )
        token_response.raise_for_status()
    except requests.RequestException as exc:
        raise ExternalServiceError("Google DWD token request failed.") from exc
    return str(token_response.json()["access_token"])


def build_drive_service(access_token: str):
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("google-api-python-client is required for Drive API access.") from exc

    return build("drive", "v3", credentials=Credentials(token=access_token), cache_discovery=False)
