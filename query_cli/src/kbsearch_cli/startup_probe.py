from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from kbsearch_cli.config import QueryCliConfig
from kbsearch_cli.credential_store import CredentialStore
from kbsearch_cli.errors import AuthenticationError, ConfigError, ExternalServiceError
from kbsearch_cli.factories import (
    _is_explicitly_invalid_token_error,
    build_drive_service,
    get_google_credential_store,
    load_google_credentials,
)

CreateDriveService = Callable[[QueryCliConfig], Any]


@dataclass(frozen=True)
class StartupProbeResult:
    secure_backend_base_url: str
    google_oauth_client_config: Path
    google_drive_authenticated: bool
    cjk_font_path: Path


def probe_startup_environment(
    config: QueryCliConfig,
    *,
    create_drive_service: CreateDriveService | None = None,
    credential_store: CredentialStore | None = None,
    probe_secure_backend: bool = True,
) -> StartupProbeResult:
    """Verify local tools and external services before running a query."""
    _probe_local_tools(config)
    if probe_secure_backend:
        _probe_secure_backend(config)
    _probe_google_drive(
        config,
        create_drive_service=create_drive_service,
        credential_store=credential_store,
    )
    return StartupProbeResult(
        secure_backend_base_url=config.secure_backend_base_url,
        google_oauth_client_config=config.google_oauth_client_config,
        google_drive_authenticated=True,
        cjk_font_path=config.cjk_font_path,
    )


def _probe_local_tools(config: QueryCliConfig) -> None:
    if shutil.which("soffice") is None:
        raise ConfigError("LibreOffice command not found in PATH: soffice")
    if not config.cjk_font_path.is_file():
        raise ConfigError(f"CJK font not found: {config.cjk_font_path}")


def _probe_secure_backend(config: QueryCliConfig) -> None:
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("requests is required for secure backend calls.") from exc

    health_url = f"{config.secure_backend_base_url.rstrip('/')}/healthz"
    try:
        response = requests.get(
            health_url,
            headers={"X-API-Key": config.secure_backend_api_key},
            timeout=(10, 30),
        )
    except requests.RequestException as exc:
        raise ExternalServiceError(f"Secure backend unreachable ({health_url}): {exc}") from exc
    if response.status_code == 401:
        raise ConfigError("Secure backend API key was rejected.")
    if response.status_code >= 400:
        raise ExternalServiceError(
            f"Secure backend health check failed ({health_url}): HTTP {response.status_code}"
        )


def _probe_google_drive(
    config: QueryCliConfig,
    *,
    create_drive_service: CreateDriveService | None,
    credential_store: CredentialStore | None,
) -> None:
    store = credential_store or get_google_credential_store()
    credentials = load_google_credentials(store)
    if credentials is None:
        raise AuthenticationError(
            "Google Drive authentication is required; run `kbsearch login`."
        )
    drive_service = (
        create_drive_service(config)
        if create_drive_service is not None
        else build_drive_service(credentials)
    )
    try:
        drive_service.about().get(fields="user/emailAddress").execute()
    except Exception as exc:
        if _is_explicitly_invalid_token_error(exc):
            store.delete()
            raise AuthenticationError(
                "Google Drive authentication has expired; run `kbsearch login`."
            ) from exc
        raise ExternalServiceError(f"Google Drive validation failed: {exc}") from exc
