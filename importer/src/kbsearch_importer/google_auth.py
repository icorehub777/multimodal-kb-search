from __future__ import annotations

import json
import time
from collections.abc import Callable
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
    token, _expires_at = get_dwd_access_token_with_expiry(
        service_account_email=service_account_email,
        subject_email=subject_email,
        scope=scope,
    )
    return token


def get_dwd_access_token_with_expiry(
    service_account_email: str,
    subject_email: str,
    *,
    scope: str = DEFAULT_DRIVE_SCOPE,
) -> tuple[str, int]:
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
    expires_at = iat + 3600
    payload: dict[str, Any] = {
        "iss": service_account_email,
        "sub": subject_email,
        "aud": TOKEN_AUDIENCE,
        "iat": iat,
        "exp": expires_at,
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
    return str(token_response.json()["access_token"]), expires_at


def build_drive_service(access_token: str):
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("google-api-python-client is required for Drive API access.") from exc

    return build("drive", "v3", credentials=Credentials(token=access_token), cache_discovery=False)


class GoogleDriveServiceProvider:
    def __init__(
        self,
        service_account_email: str,
        subject_email: str,
        *,
        token_factory: Callable[[], tuple[str, int]] | None = None,
        service_builder: Callable[[str], Any] | None = None,
        clock: Callable[[], float] | None = None,
        refresh_margin_seconds: int = 300,
    ) -> None:
        self._token_factory = token_factory or (
            lambda: get_dwd_access_token_with_expiry(
                service_account_email=service_account_email,
                subject_email=subject_email,
            )
        )
        self._service_builder = service_builder or build_drive_service
        self._clock = clock or time.time
        self._refresh_margin_seconds = refresh_margin_seconds
        self._service: Any | None = None
        self._expires_at = 0

    def get_service(self) -> Any:
        if self._service is not None and self._clock() < self._expires_at - self._refresh_margin_seconds:
            return self._service

        token, expires_at = self._token_factory()
        self._service = self._service_builder(token)
        self._expires_at = expires_at
        return self._service

    def files(self) -> Any:
        return self.get_service().files()
