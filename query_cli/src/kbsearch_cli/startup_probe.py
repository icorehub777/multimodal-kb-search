from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from kbsearch_cli.config import ConfigError, QueryCliConfig
from kbsearch_cli.errors import ExternalServiceError
from kbsearch_cli.factories import discard_oauth_token_cache, load_google_credentials
from kbsearch_cli.logging_config import LOGGER_NAME

CreateDriveService = Callable[[QueryCliConfig], Any]
logger = logging.getLogger(LOGGER_NAME)


@dataclass(frozen=True)
class StartupProbeResult:
    secure_backend_base_url: str
    google_oauth_client_config: Path
    google_oauth_token_cache: Path
    google_drive_authenticated: bool
    cjk_font_path: Path | None
    render_downloaded_files: bool


def probe_startup_environment(
    config: QueryCliConfig,
    *,
    create_drive_service: CreateDriveService | None = None,
) -> StartupProbeResult:
    """Verify local config paths and external services before running a query."""
    _probe_local_tools(config)
    _probe_secure_backend(config)
    google_drive_authenticated = _probe_google_drive_if_configured(
        config,
        create_drive_service=create_drive_service,
    )
    return StartupProbeResult(
        secure_backend_base_url=config.secure_backend_base_url,
        google_oauth_client_config=config.google_oauth_client_config,
        google_oauth_token_cache=config.google_oauth_token_cache,
        google_drive_authenticated=google_drive_authenticated,
        cjk_font_path=config.cjk_font_path,
        render_downloaded_files=config.render_downloaded_files,
    )


def _probe_local_tools(config: QueryCliConfig) -> None:
    if not config.google_oauth_client_config.is_file():
        raise ConfigError(
            f"Google OAuth client not found: {config.google_oauth_client_config}"
        )
    if not config.render_downloaded_files:
        return
    if config.cjk_font_path is None:
        raise ConfigError("Render tools are required when downloaded file rendering is enabled.")
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
        response = requests.get(health_url, timeout=10)
    except requests.RequestException as exc:
        raise ExternalServiceError(f"Secure backend unreachable ({health_url}): {exc}") from exc
    if response.status_code >= 400:
        raise ExternalServiceError(
            f"Secure backend health check failed ({health_url}): HTTP {response.status_code}"
        )


def _probe_google_drive_if_configured(
    config: QueryCliConfig,
    *,
    create_drive_service: CreateDriveService | None = None,
) -> bool:
    if not config.google_oauth_token_cache.exists():
        return False

    credentials = load_google_credentials(config)
    if credentials is None:
        return False

    if create_drive_service is not None:
        drive_service = create_drive_service(config)
    else:
        from kbsearch_cli.factories import build_drive_service

        drive_service = build_drive_service(credentials)

    try:
        drive_service.about().get(fields="user/emailAddress").execute()
    except Exception as exc:
        if discard_oauth_token_cache(config):
            logger.warning(
                "Removed Google OAuth token cache after Drive validation failed (%s): %s",
                config.google_oauth_token_cache,
                exc,
            )
        return False
    return True
