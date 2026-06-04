from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from kbsearch_cli.backend_client import SecureBackendClient
from kbsearch_cli.config import ConfigError, QueryCliConfig
from kbsearch_cli.errors import ExternalServiceError
from kbsearch_cli.google_drive import GoogleDriveQueryClient
from kbsearch_cli.logging_config import LOGGER_NAME
from kbsearch_cli.orchestrator import QueryOrchestrator
from kbsearch_cli.output import QueryResultWriter
from kbsearch_cli.rendering import DocumentPageRenderer

DRIVE_SCOPES = ("https://www.googleapis.com/auth/drive.readonly",)
logger = logging.getLogger(LOGGER_NAME)


def create_query_orchestrator(config: QueryCliConfig) -> QueryOrchestrator:
    return QueryOrchestrator(
        google_drive=GoogleDriveQueryClient(_create_drive_service(config)),
        backend=SecureBackendClient(config.secure_backend_base_url),
        result_writer=QueryResultWriter(config.query_results_root, clock=_timestamp),
        page_renderer=DocumentPageRenderer(
            libreoffice_command=config.libreoffice_command,
            cjk_font_path=config.cjk_font_path,
        ),
    )


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def discard_oauth_token_cache(config: QueryCliConfig) -> bool:
    token_cache = config.google_oauth_token_cache
    if not token_cache.exists():
        return False
    token_cache.unlink()
    return True


def load_google_credentials(config: QueryCliConfig):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise RuntimeError(
            "google-auth-oauthlib and google-api-python-client are required for Google Drive OAuth."
        ) from exc

    if not config.google_oauth_token_cache.exists():
        return None

    try:
        credentials = Credentials.from_authorized_user_file(
            str(config.google_oauth_token_cache),
            scopes=DRIVE_SCOPES,
        )
    except OSError as exc:
        if discard_oauth_token_cache(config):
            logger.warning(
                "Removed unreadable Google OAuth token cache (%s): %s",
                config.google_oauth_token_cache,
                exc,
            )
        return None

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            config.google_oauth_token_cache.write_text(credentials.to_json(), encoding="utf-8")
        except Exception as exc:
            if discard_oauth_token_cache(config):
                logger.warning(
                    "Removed Google OAuth token cache after refresh failure (%s): %s",
                    config.google_oauth_token_cache,
                    exc,
                )
            return None
    elif not credentials.valid:
        if discard_oauth_token_cache(config):
            logger.warning(
                "Removed invalid Google OAuth token cache: %s",
                config.google_oauth_token_cache,
            )
        return None

    return credentials


def build_drive_service(credentials) -> Any:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "google-api-python-client is required for Google Drive OAuth."
        ) from exc

    return build("drive", "v3", credentials=credentials)


def _create_drive_service(config: QueryCliConfig):
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError(
            "google-auth-oauthlib and google-api-python-client are required for Google Drive OAuth."
        ) from exc

    credentials = load_google_credentials(config)
    if credentials is None or not credentials.valid:
        if not config.google_oauth_client_config.is_file():
            raise ConfigError(
                f"Google OAuth client not found: {config.google_oauth_client_config}"
            )
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(config.google_oauth_client_config),
                scopes=DRIVE_SCOPES,
            )
            credentials = flow.run_local_server(port=0)
        except OSError as exc:
            raise ConfigError(
                f"Google OAuth client not found: {config.google_oauth_client_config}"
            ) from exc
        except Exception as exc:
            raise ExternalServiceError(f"Google Drive authentication failed: {exc}") from exc

        config.google_oauth_token_cache.parent.mkdir(parents=True, exist_ok=True)
        config.google_oauth_token_cache.write_text(credentials.to_json(), encoding="utf-8")
        logger.info(
            "Google OAuth token cache created at %s",
            config.google_oauth_token_cache,
        )

    return build_drive_service(credentials)
