from __future__ import annotations

from datetime import datetime

from kbsearch_cli.backend_client import SecureBackendClient
from kbsearch_cli.config import QueryCliConfig
from kbsearch_cli.google_drive import GoogleDriveQueryClient
from kbsearch_cli.orchestrator import QueryOrchestrator
from kbsearch_cli.output import QueryResultWriter
from kbsearch_cli.rendering import DocumentPageRenderer

DRIVE_SCOPES = ("https://www.googleapis.com/auth/drive.readonly",)


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


def _create_drive_service(config: QueryCliConfig):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "google-auth-oauthlib and google-api-python-client are required for Google Drive OAuth."
        ) from exc

    credentials = None
    if config.google_oauth_token_cache.exists():
        credentials = Credentials.from_authorized_user_file(
            str(config.google_oauth_token_cache),
            scopes=DRIVE_SCOPES,
        )
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(config.google_oauth_client_config),
                scopes=DRIVE_SCOPES,
            )
            credentials = flow.run_local_server(port=0)
        config.google_oauth_token_cache.parent.mkdir(parents=True, exist_ok=True)
        config.google_oauth_token_cache.write_text(credentials.to_json(), encoding="utf-8")

    return build("drive", "v3", credentials=credentials)
