from __future__ import annotations

from kbsearch_importer.config import ImporterConfig
from kbsearch_importer.conversion import DocumentConverter, PdfPageRenderer
from kbsearch_importer.dashscope_embedder import DashScopeImageEmbeddingClient, DashScopePageEmbedder
from kbsearch_importer.document_importer import PipelineDocumentImporter
from kbsearch_importer.google_auth import GoogleDriveServiceProvider
from kbsearch_importer.google_drive import GoogleDriveDownloader, GoogleDriveScanner
from kbsearch_importer.orchestrator import SyncOrchestrator
from kbsearch_importer.qdrant_index import QdrantIndexAdapter


def create_drive_scanner(config: ImporterConfig) -> GoogleDriveScanner:
    service = create_drive_service_provider(config)
    return GoogleDriveScanner(service, config.google_drive_sources)


def create_drive_downloader(config: ImporterConfig) -> GoogleDriveDownloader:
    service = create_drive_service_provider(config)
    return GoogleDriveDownloader(service)


def create_drive_service_provider(config: ImporterConfig) -> GoogleDriveServiceProvider:
    return GoogleDriveServiceProvider(
        service_account_email=config.google_service_account_email,
        subject_email=config.google_dwd_subject_email,
    )


def create_qdrant_index(config: ImporterConfig) -> QdrantIndexAdapter:
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise RuntimeError("qdrant-client is required for Qdrant operations.") from exc

    return QdrantIndexAdapter(
        client=QdrantClient(url=config.qdrant_url, api_key=config.qdrant_api_key),
        collection=config.qdrant_collection,
    )


def create_page_embedder(config: ImporterConfig) -> DashScopePageEmbedder:
    return DashScopePageEmbedder(
        client=DashScopeImageEmbeddingClient(
            api_key=config.dashscope_api_key,
            model=config.dashscope_embedding_model,
            dimension=config.dashscope_vector_size,
        ),
        expected_dimension=config.dashscope_vector_size,
    )


def create_sync_orchestrator(config: ImporterConfig) -> SyncOrchestrator:
    qdrant_index = create_qdrant_index(config)
    drive_service = create_drive_service_provider(config)
    return SyncOrchestrator(
        workspace_scanner=GoogleDriveScanner(drive_service, config.google_drive_sources),
        qdrant_index=qdrant_index,
        document_importer=PipelineDocumentImporter(
            downloader=GoogleDriveDownloader(drive_service),
            converter=DocumentConverter(libreoffice_command=config.libreoffice_command),
            renderer=PdfPageRenderer(),
            embedder=create_page_embedder(config),
            qdrant_index=qdrant_index,
            work_dir=config.importer_root / "work",
            keep_success_work_files=config.keep_success_work_files,
            keep_failed_work_files=config.keep_failed_work_files,
        ),
    )
