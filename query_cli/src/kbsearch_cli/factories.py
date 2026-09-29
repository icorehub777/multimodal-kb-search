from __future__ import annotations

import json
import logging
from typing import Any

from kbsearch_cli.backend_client import SecureBackendClient
from kbsearch_cli.config import QueryCliConfig
from kbsearch_cli.credential_store import CredentialStore, WindowsCredentialStore
from kbsearch_cli.errors import AuthenticationError, ConfigError, ExternalServiceError
from kbsearch_cli.google_drive import GoogleDriveQueryClient
from kbsearch_cli.logging_config import LOGGER_NAME
from kbsearch_cli.orchestrator import QueryOrchestrator
from kbsearch_cli.output import QueryResultWriter
from kbsearch_cli.rendering import DocumentPageRenderer

DRIVE_SCOPES = ("https://www.googleapis.com/auth/drive.readonly",)
logger = logging.getLogger(LOGGER_NAME)


def create_query_orchestrator(config: QueryCliConfig) -> QueryOrchestrator:
    return QueryOrchestrator(
        google_drive=GoogleDriveQueryClient(create_drive_service(config)),
        backend=SecureBackendClient(
            config.secure_backend_base_url,
            config.secure_backend_api_key,
        ),
        result_writer=QueryResultWriter(),
        document_processor=DocumentPageRenderer(cjk_font_path=config.cjk_font_path),
    )


def get_google_credential_store() -> CredentialStore:
    return WindowsCredentialStore()


def _is_explicitly_invalid_token_error(exc: Exception) -> bool:
    response = getattr(exc, "resp", None)
    if getattr(response, "status", None) == 401:
        return True
    message = str(exc).lower()
    return any(marker in message for marker in ("invalid_grant", "invalid_token", "revoked"))


def load_google_credentials(credential_store: CredentialStore | None = None):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise RuntimeError(
            "google-auth and google-api-python-client are required for Google Drive OAuth."
        ) from exc

    store = credential_store or get_google_credential_store()
    serialized = store.read()
    if serialized is None:
        return None
    try:
        payload = json.loads(serialized)
        if not isinstance(payload, dict):
            raise ValueError("credential payload must be an object")
        credentials = Credentials.from_authorized_user_info(payload, scopes=DRIVE_SCOPES)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AuthenticationError(
            "Stored Google authentication data is invalid; run `kbsearch login`."
        ) from exc

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except Exception as exc:
            if _is_explicitly_invalid_token_error(exc):
                store.delete()
                logger.warning("Removed invalid Google OAuth credential.")
                return None
            raise ExternalServiceError(f"Google OAuth token refresh failed: {exc}") from exc
        store.write(credentials.to_json())
    elif not credentials.valid:
        raise AuthenticationError(
            "Google authentication is invalid; run `kbsearch login`."
        )
    return credentials


def build_drive_service(credentials) -> Any:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("google-api-python-client is required for Google Drive OAuth.") from exc
    return build("drive", "v3", credentials=credentials)


def create_drive_service(
    config: QueryCliConfig,
    *,
    credential_store: CredentialStore | None = None,
):
    credentials = load_google_credentials(credential_store)
    if credentials is None:
        raise AuthenticationError(
            "Google Drive authentication is required; run `kbsearch login`."
        )
    return build_drive_service(credentials)


def login_google_drive(
    config: QueryCliConfig,
    *,
    credential_store: CredentialStore | None = None,
):
    if not config.google_oauth_client_config.is_file():
        raise ConfigError(f"Google OAuth client not found: {config.google_oauth_client_config}")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError("google-auth-oauthlib is required for Google Drive OAuth.") from exc
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(config.google_oauth_client_config), scopes=DRIVE_SCOPES
        )
        credentials = flow.run_local_server(port=0)
    except OSError as exc:
        raise ConfigError(f"Google OAuth client not found: {config.google_oauth_client_config}") from exc
    except Exception as exc:
        raise ExternalServiceError(f"Google Drive authentication failed: {exc}") from exc
    (credential_store or get_google_credential_store()).write(credentials.to_json())
    logger.info("Google OAuth credential stored in Windows Credential Manager.")
    return credentials
