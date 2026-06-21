from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from app.config import load_importer_config
from app.conversion import DocumentConverter, PdfPageRenderer
from app.dashscope_embedder import DashScopeImageEmbeddingClient
from app.factories import (
    create_drive_downloader,
    create_drive_scanner,
    create_qdrant_index,
    create_sync_orchestrator,
)
from app.metadata import build_page_vector_metadata
from app.models import WorkspaceDocument


TINY_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def probe_config() -> None:
    config = load_importer_config()
    print(f"config: ok sources={len(config.google_drive_sources)} collection={config.qdrant_collection}")


def probe_google() -> None:
    config = load_importer_config()
    scanner = create_drive_scanner(config)
    documents = scanner.list_documents()
    print(f"google: ok documents={len(documents)}")
    for document in documents[:5]:
        print(
            "google: sample "
            f"file_id={document.file_id} name={document.name} version={document.version} "
            f"mime_type={document.mime_type}"
        )


def probe_dashscope() -> None:
    config = load_importer_config()
    client = DashScopeImageEmbeddingClient(
        api_key=config.dashscope_api_key,
        model=config.dashscope_embedding_model,
        dimension=config.dashscope_vector_size,
        image_max_bytes=config.dashscope_image_max_bytes,
        jpeg_quality=config.dashscope_jpeg_quality,
    )
    with TemporaryDirectory() as temp_dir:
        image_path = Path(temp_dir) / "sample.png"
        image_path.write_bytes(base64.b64decode(TINY_PNG_BASE64))
        vector = client.embed_image(image_path)
    print(f"dashscope: ok dimension={len(vector)}")


def probe_qdrant() -> None:
    config = load_importer_config()
    index = create_qdrant_index(config)
    existing = index.list_documents()
    print(f"qdrant: ok existing_documents={len(existing)}")

    probe_document = WorkspaceDocument(
        file_id="kbsearch-importer-probe",
        name="kbsearch-importer-probe.pdf",
        location="/probe/kbsearch-importer-probe.pdf",
        web_url="https://example.invalid/kbsearch-importer-probe",
        version="probe",
        modified_time="2026-05-24T00:00:00Z",
        mime_type="application/pdf",
    )
    metadata = build_page_vector_metadata(
        document=probe_document,
        page_number=1,
    )
    vector = [0.0] * config.qdrant_vector_size
    index.upsert_page_vectors([(vector, metadata)])
    index.delete_document(probe_document.file_id)
    print("qdrant: write_delete_probe=ok")


def probe_sync_decisions() -> None:
    config = load_importer_config()
    scanner = create_drive_scanner(config)
    index = create_qdrant_index(config)
    documents = scanner.list_documents()
    if len(documents) < 2:
        raise RuntimeError("sync decision probe requires at least two Google Drive documents")

    added_document = documents[0]
    changed_document = documents[1]
    deleted_probe = WorkspaceDocument(
        file_id="kbsearch-importer-deleted-probe",
        name="kbsearch-importer-deleted-probe.pdf",
        location="/probe/kbsearch-importer-deleted-probe.pdf",
        web_url="https://example.invalid/kbsearch-importer-deleted-probe",
        version="deleted-probe",
        modified_time="2026-05-24T00:00:00Z",
        mime_type="application/pdf",
    )

    index.delete_document(added_document.file_id)
    index.delete_document(changed_document.file_id)
    index.delete_document(deleted_probe.file_id)

    stale_metadata = build_page_vector_metadata(
        document=WorkspaceDocument(
            file_id=changed_document.file_id,
            name=changed_document.name,
            location=changed_document.location,
            web_url=changed_document.web_url,
            version=changed_document.version,
            modified_time="1970-01-01T00:00:00Z",
            mime_type=changed_document.mime_type,
        ),
        page_number=1,
    )
    deleted_metadata = build_page_vector_metadata(
        document=deleted_probe,
        page_number=1,
    )
    vector = [0.0] * config.qdrant_vector_size
    index.upsert_page_vectors([(vector, stale_metadata), (vector, deleted_metadata)])

    summary = create_sync_orchestrator(config).run()
    print(
        "sync-decisions: "
        f"imported={summary.imported} deleted={summary.deleted} "
        f"reimported={summary.reimported} skipped={summary.skipped}"
    )
    if summary.imported != 1 or summary.deleted != 1 or summary.reimported != 1:
        raise RuntimeError("sync decision summary did not match expected import/delete/reimport counts")


def probe_libreoffice() -> None:
    docx_mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / "sample.docx"
        _write_minimal_docx(source_path)
        output_path = DocumentConverter().convert_to_pdf(
            source_path,
            docx_mime_type,
            temp_path / "out",
        )
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("LibreOffice conversion did not create a non-empty PDF")
        print(f"libreoffice: ok output={output_path.name} bytes={output_path.stat().st_size}")


def probe_document_processing() -> None:
    config = load_importer_config()
    scanner = create_drive_scanner(config)
    downloader = create_drive_downloader(config)
    converter = DocumentConverter()
    renderer = PdfPageRenderer()
    documents = scanner.list_documents()
    if not documents:
        raise RuntimeError("document processing probe found no Google Drive documents")

    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        for document in documents:
            document_dir = root / document.file_id
            source_file = downloader.download(
                file_id=document.file_id,
                name=document.name,
                mime_type=document.mime_type,
                output_dir=document_dir / "source",
            )
            render_source = converter.convert_to_pdf(
                source_file,
                document.mime_type,
                document_dir / "pdf",
            )
            pages = renderer.render_pages(render_source, document_dir / "pages")
            if not pages:
                raise RuntimeError(f"no pages rendered for file_id={document.file_id}")
            for page in pages:
                if not page.path.exists() or page.path.stat().st_size == 0:
                    raise RuntimeError(
                        f"empty rendered page for file_id={document.file_id} page={page.page_number}"
                    )
            print(
                "document-processing: ok "
                f"file_id={document.file_id} name={document.name} "
                f"mime_type={document.mime_type} pages={len(pages)}"
            )


def _write_minimal_docx(path: Path) -> None:
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/>'
            "</Relationships>"
        ),
        "word/document.xml": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>KBSearch LibreOffice conversion probe</w:t></w:r></w:p></w:body>"
            "</w:document>"
        ),
    }
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for file_name, content in files.items():
            archive.writestr(file_name, content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "target",
        choices=(
            "config",
            "google",
            "dashscope",
            "qdrant",
            "sync-decisions",
            "libreoffice",
            "document-processing",
            "all",
        ),
    )
    args = parser.parse_args(argv)

    probes = {
        "config": [probe_config],
        "google": [probe_google],
        "dashscope": [probe_dashscope],
        "qdrant": [probe_qdrant],
        "sync-decisions": [probe_sync_decisions],
        "libreoffice": [probe_libreoffice],
        "document-processing": [probe_document_processing],
        "all": [probe_config, probe_google, probe_dashscope, probe_qdrant],
    }

    try:
        for probe in probes[args.target]:
            probe()
    except Exception as exc:
        print(f"probe failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
