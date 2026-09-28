from __future__ import annotations

import time
from collections.abc import Callable
from datetime import timezone
from typing import Any

from app.errors import ExternalServiceError
from app.google_credentials import ensure_google_application_credentials

DEFAULT_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"


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
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError as exc:
        raise RuntimeError("google-auth is required for Google Workspace authentication.") from exc

    adc_path = ensure_google_application_credentials()

    try:
        credentials = service_account.Credentials.from_service_account_file(
            adc_path,
            scopes=[scope],
            subject=subject_email,
        )
        if credentials.service_account_email != service_account_email:
            raise ExternalServiceError(
                "Service account email mismatch between JSON client_email and configured identity."
            )
        credentials.refresh(Request())
    except ExternalServiceError:
        raise
    except Exception as exc:
        message = (
            "Google Domain-Wide Delegation credential refresh failed. "
            "Verify gcp-adc.json, GOOGLE_DWD_SUBJECT_EMAIL, and Workspace DWD scopes."
        )
        if _looks_like_network_or_dns_error(exc):
            message += (
                " The underlying refresh error looks like a network/DNS failure; "
                "verify that the importer container can resolve and reach oauth2.googleapis.com."
            )
        raise ExternalServiceError(message) from exc

    token = credentials.token
    if not token:
        raise ExternalServiceError("Google Domain-Wide Delegation returned an empty access token.")

    expiry = credentials.expiry
    if expiry is None:
        expires_at = int(time.time()) + 3600
    else:
        expires_at = int(expiry.replace(tzinfo=timezone.utc).timestamp())

    return str(token), expires_at


def _looks_like_network_or_dns_error(exc: Exception) -> bool:
    text = str(exc).lower()
    indicators = (
        "failed to resolve",
        "name or service not known",
        "no address associated with hostname",
        "nameresolutionerror",
        "temporary failure in name resolution",
        "connectionerror",
        "transporterror",
    )
    return any(indicator in text for indicator in indicators)


def build_drive_service(access_token: str):
    try:
        import httplib2
        from google_auth_httplib2 import AuthorizedHttp
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("google-api-python-client is required for Drive API access.") from exc

    credentials = Credentials(token=access_token)
    authorized_http = AuthorizedHttp(credentials, http=httplib2.Http(timeout=60))
    return build("drive", "v3", http=authorized_http, cache_discovery=False)


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
