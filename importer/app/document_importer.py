from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from time import monotonic
import shutil
from typing import Protocol

from app.document_processing import UnsupportedDocumentTypeError
from app.errors import DocumentImportError, ImporterError
from app.logging_config import LOGGER_NAME
from app.metadata import build_page_vector_metadata
from app.models import PageVectorMetadata, WorkspaceDocument

SKIPPABLE_DOCUMENT_FAILURES: tuple[type[Exception], ...] = (
    ImporterError,
    UnsupportedDocumentTypeError,
    OSError,
)
EMBEDDING_PROGRESS_INTERVAL_SECONDS = 30


@dataclass(frozen=True)
class PageImage:
    page_number: int
    path: Path


class Downloader(Protocol):
    def download(self, file_id: str, name: str, mime_type: str, output_dir: Path) -> Path:
        raise NotImplementedError


class Converter(Protocol):
    def convert_to_pdf(self, source_path: Path, mime_type: str, output_dir: Path) -> Path:
        raise NotImplementedError


class Renderer(Protocol):
    def render_pages(self, pdf_path: Path, output_dir: Path) -> list[PageImage]:
        raise NotImplementedError


class Embedder(Protocol):
    def embed_page_image(self, image_path: Path) -> list[float]:
        raise NotImplementedError


class VectorIndex(Protocol):
    def upsert_page_vectors(
        self,
        pages: list[tuple[list[float] | tuple[float, ...], PageVectorMetadata]],
    ) -> int:
        raise NotImplementedError


class PipelineDocumentImporter:
    def __init__(
        self,
        downloader: Downloader,
        converter: Converter,
        renderer: Renderer,
        embedder: Embedder,
        qdrant_index: VectorIndex,
        work_dir: Path,
        keep_success_work_files: bool = True,
        keep_failed_work_files: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        self._downloader = downloader
        self._converter = converter
        self._renderer = renderer
        self._embedder = embedder
        self._qdrant_index = qdrant_index
        self._work_dir = work_dir
        self._keep_success_work_files = keep_success_work_files
        self._keep_failed_work_files = keep_failed_work_files
        self._logger = logger or logging.getLogger(LOGGER_NAME)

    def import_document(self, document: WorkspaceDocument) -> int:
        self._logger.info(
            "file_id=%s name=%s stage=import status=started mime_type=%s version=%s",
            document.file_id,
            document.name,
            document.mime_type,
            document.version,
        )
        document_dir = self._work_dir / document.file_id
        source_dir = document_dir / "source"
        pdf_dir = document_dir / "pdf"
        page_dir = document_dir / "pages"

        try:
            try:
                source_file = self._downloader.download(
                    file_id=document.file_id,
                    name=document.name,
                    mime_type=document.mime_type,
                    output_dir=source_dir,
                )
            except Exception as exc:
                _raise_document_import_error(
                    self._logger,
                    document,
                    stage="download",
                    exc=exc,
                    message=f"download failed for file_id={document.file_id}",
                )
            self._logger.debug(
                "file_id=%s name=%s stage=download status=success path=%s",
                document.file_id,
                document.name,
                source_file,
            )

            try:
                pdf_file = self._converter.convert_to_pdf(source_file, document.mime_type, pdf_dir)
            except Exception as exc:
                _raise_document_import_error(
                    self._logger,
                    document,
                    stage="convert",
                    exc=exc,
                    message=f"conversion failed for file_id={document.file_id}",
                )
            self._logger.debug(
                "file_id=%s name=%s stage=convert status=success path=%s",
                document.file_id,
                document.name,
                pdf_file,
            )

            try:
                page_images = self._renderer.render_pages(pdf_file, page_dir)
            except Exception as exc:
                _raise_document_import_error(
                    self._logger,
                    document,
                    stage="render",
                    exc=exc,
                    message=f"page rendering failed for file_id={document.file_id}",
                )
            self._logger.debug(
                "file_id=%s name=%s stage=render status=success page_count=%s",
                document.file_id,
                document.name,
                len(page_images),
            )

            pages: list[tuple[list[float], PageVectorMetadata]] = []
            last_progress_at = monotonic()
            for page_image in page_images:
                try:
                    vector = self._embedder.embed_page_image(page_image.path)
                except Exception as exc:
                    _raise_document_import_error(
                        self._logger,
                        document,
                        stage="embed",
                        exc=exc,
                        message=(
                            "embedding failed for "
                            f"file_id={document.file_id} page={page_image.page_number}"
                        ),
                        page_number=page_image.page_number,
                        page_total=len(page_images),
                    )
                metadata = build_page_vector_metadata(
                    document=document,
                    page_number=page_image.page_number,
                )
                pages.append((vector, metadata))
                self._logger.debug(
                    "file_id=%s name=%s stage=embed status=progress page=%s total=%s",
                    document.file_id,
                    document.name,
                    page_image.page_number,
                    len(page_images),
                )
                now = monotonic()
                if now - last_progress_at >= EMBEDDING_PROGRESS_INTERVAL_SECONDS:
                    self._logger.info(
                        "file_id=%s name=%s stage=embed status=progress page=%s total=%s",
                        document.file_id,
                        document.name,
                        page_image.page_number,
                        len(page_images),
                    )
                    last_progress_at = now
            self._logger.debug(
                "file_id=%s name=%s stage=embed status=success page_count=%s",
                document.file_id,
                document.name,
                len(pages),
            )

            try:
                imported_pages = self._qdrant_index.upsert_page_vectors(pages)
            except Exception as exc:
                _raise_document_import_error(
                    self._logger,
                    document,
                    stage="upsert",
                    exc=exc,
                    message=f"qdrant upsert failed for file_id={document.file_id}",
                )
            self._logger.debug(
                "file_id=%s name=%s stage=upsert status=success vector_count=%s",
                document.file_id,
                document.name,
                imported_pages,
            )
        except Exception:
            if not self._keep_failed_work_files:
                _remove_document_dir(document_dir)
            raise

        if not self._keep_success_work_files:
            _remove_document_dir(document_dir)
        return imported_pages


def _log_stage_failure(
    logger: logging.Logger,
    document: WorkspaceDocument,
    *,
    stage: str,
    exc: Exception,
    page_number: int | None = None,
    page_total: int | None = None,
) -> None:
    page_label = page_number if page_number is not None else "-"
    total_label = page_total if page_total is not None else "-"
    logger.exception(
        "file_id=%s name=%s stage=%s status=failed page=%s total=%s "
        "error_type=%s error_message=%s",
        document.file_id,
        document.name,
        stage,
        page_label,
        total_label,
        exc.__class__.__name__,
        exc,
    )


def _raise_document_import_error(
    logger: logging.Logger,
    document: WorkspaceDocument,
    *,
    stage: str,
    exc: Exception,
    message: str,
    page_number: int | None = None,
    page_total: int | None = None,
) -> None:
    if isinstance(exc, DocumentImportError):
        raise exc
    if not isinstance(exc, SKIPPABLE_DOCUMENT_FAILURES):
        raise exc
    _log_stage_failure(
        logger,
        document,
        stage=stage,
        exc=exc,
        page_number=page_number,
        page_total=page_total,
    )
    raise DocumentImportError(message, stage=stage, page_number=page_number) from exc


def _remove_document_dir(document_dir: Path) -> None:
    if document_dir.exists():
        shutil.rmtree(document_dir)
