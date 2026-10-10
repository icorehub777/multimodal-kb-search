from __future__ import annotations

import logging

from kbsearch_importer.config import ImporterConfig
from kbsearch_importer.conversion import DocumentConverter, PdfPageRenderer
from kbsearch_importer.dashscope_embedder import DashScopeImageEmbeddingClient, DashScopePageEmbedder
from kbsearch_importer.document_importer import PipelineDocumentImporter
from kbsearch_importer.google_auth import GoogleDriveServiceProvider
from kbsearch_importer.google_credentials import load_service_account_email
from kbsearch_importer.google_drive import GoogleDriveDownloader, GoogleDriveScanner
from kbsearch_importer.logging_config import LOGGER_NAME
from kbsearch_importer.orchestrator import SyncOrchestrator
from kbsearch_importer.qdrant_client_factory import build_qdrant_client
from kbsearch_importer.qdrant_index import QdrantIndexAdapter


def create_drive_scanner(config: ImporterConfig) -> GoogleDriveScanner:
    service = create_drive_service_provider(config)
    return GoogleDriveScanner(service, config.google_drive_sources)


def create_drive_downloader(config: ImporterConfig) -> GoogleDriveDownloader:
    service = create_drive_service_provider(config)
    return GoogleDriveDownloader(service)


def create_drive_service_provider(config: ImporterConfig) -> GoogleDriveServiceProvider:
    return GoogleDriveServiceProvider(
        service_account_email=load_service_account_email(),
        subject_email=config.google_dwd_subject_email,
    )


def create_qdrant_index(config: ImporterConfig) -> QdrantIndexAdapter:
    return QdrantIndexAdapter(
        client=build_qdrant_client(config.qdrant_url, config.qdrant_api_key),
        collection=config.qdrant_collection,
    )


def create_page_embedder(config: ImporterConfig) -> DashScopePageEmbedder:
    return DashScopePageEmbedder(
        client=DashScopeImageEmbeddingClient(
            api_key=config.dashscope_api_key,
            model=config.dashscope_embedding_model,
            dimension=config.vector_size,
            image_max_bytes=config.dashscope_image_max_bytes,
            jpeg_quality=config.dashscope_jpeg_quality,
            logger=logging.getLogger(LOGGER_NAME),
        ),
        expected_dimension=config.vector_size,
    )


def create_sync_orchestrator(config: ImporterConfig) -> SyncOrchestrator:
    logger = logging.getLogger(LOGGER_NAME)
    qdrant_index = create_qdrant_index(config)
    drive_service = create_drive_service_provider(config)
    return SyncOrchestrator(
        workspace_scanner=GoogleDriveScanner(drive_service, config.google_drive_sources),
        qdrant_index=qdrant_index,
        document_importer=PipelineDocumentImporter(
            downloader=GoogleDriveDownloader(drive_service),
            converter=DocumentConverter(
                cjk_font_path=config.cjk_font_path,
                logger=logger,
            ),
            renderer=PdfPageRenderer(
                target_dpi=config.pdf_render_target_dpi,
                max_pixels=config.pdf_render_max_pixels,
                logger=logger,
            ),
            embedder=create_page_embedder(config),
            qdrant_index=qdrant_index,
            work_dir=config.app_root / "work",
            keep_success_work_files=config.keep_success_work_files,
            keep_failed_work_files=config.keep_failed_work_files,
            logger=logger,
        ),
        logger=logger,
    )
