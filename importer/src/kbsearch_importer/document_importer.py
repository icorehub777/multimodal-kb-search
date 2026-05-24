from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Protocol

from kbsearch_importer.errors import DocumentImportError
from kbsearch_importer.metadata import build_page_vector_metadata
from kbsearch_importer.models import PageVectorMetadata, WorkspaceDocument


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
    ) -> None:
        self._downloader = downloader
        self._converter = converter
        self._renderer = renderer
        self._embedder = embedder
        self._qdrant_index = qdrant_index
        self._work_dir = work_dir
        self._keep_success_work_files = keep_success_work_files
        self._keep_failed_work_files = keep_failed_work_files

    def import_document(self, document: WorkspaceDocument) -> int:
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
                raise DocumentImportError(f"download failed for file_id={document.file_id}") from exc

            try:
                pdf_file = self._converter.convert_to_pdf(source_file, document.mime_type, pdf_dir)
            except Exception as exc:
                raise DocumentImportError(f"conversion failed for file_id={document.file_id}") from exc

            try:
                page_images = self._renderer.render_pages(pdf_file, page_dir)
            except Exception as exc:
                raise DocumentImportError(f"page rendering failed for file_id={document.file_id}") from exc

            pages: list[tuple[list[float], PageVectorMetadata]] = []
            try:
                for page_image in page_images:
                    vector = self._embedder.embed_page_image(page_image.path)
                    metadata = build_page_vector_metadata(
                        document=document,
                        page_number=page_image.page_number,
                        page_image_path=page_image.path,
                        source_file_path=source_file,
                    )
                    pages.append((vector, metadata))
            except Exception as exc:
                raise DocumentImportError(f"embedding failed for file_id={document.file_id}") from exc

            try:
                imported_pages = self._qdrant_index.upsert_page_vectors(pages)
            except Exception as exc:
                raise DocumentImportError(f"qdrant upsert failed for file_id={document.file_id}") from exc
        except Exception:
            if not self._keep_failed_work_files:
                _remove_document_dir(document_dir)
            raise

        if not self._keep_success_work_files:
            _remove_document_dir(document_dir)
        return imported_pages


def _remove_document_dir(document_dir: Path) -> None:
    if document_dir.exists():
        shutil.rmtree(document_dir)
