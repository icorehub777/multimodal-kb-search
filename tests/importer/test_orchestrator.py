import unittest
from io import StringIO
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from kbsearch_importer.document_importer import PageImage, PipelineDocumentImporter
from kbsearch_importer.errors import DocumentConversionError, DocumentImportError
from kbsearch_importer.models import QdrantDocument, WorkspaceDocument
from kbsearch_importer.orchestrator import SyncOrchestrator


def workspace_doc(file_id: str, version: str) -> WorkspaceDocument:
    return WorkspaceDocument(
        file_id=file_id,
        name=f"{file_id}.pdf",
        location=f"/source/{file_id}.pdf",
        web_url=f"https://drive.google.com/file/d/{file_id}",
        version=version,
        modified_time=f"2026-05-24T00:00:0{version}Z",
        mime_type="application/pdf",
    )


class FakeWorkspaceScanner:
    def __init__(self) -> None:
        self.documents = [
            workspace_doc("added", "1"),
            workspace_doc("changed", "2"),
            workspace_doc("same", "1"),
        ]

    def list_documents(self) -> list[WorkspaceDocument]:
        return self.documents


class FakeQdrantIndex:
    def __init__(self) -> None:
        self.documents = [
            QdrantDocument(file_id="deleted", modified_time="2026-05-24T00:00:01Z"),
            QdrantDocument(file_id="changed", modified_time="2026-05-24T00:00:01Z"),
            QdrantDocument(file_id="same", modified_time="2026-05-24T00:00:01Z"),
        ]
        self.deleted: list[str] = []

    def list_documents(self) -> list[QdrantDocument]:
        return self.documents

    def delete_document(self, file_id: str) -> None:
        self.deleted.append(file_id)


class FakeDocumentImporter:
    def __init__(self) -> None:
        self.imported: list[str] = []

    def import_document(self, document: WorkspaceDocument) -> int:
        self.imported.append(document.file_id)
        return 1


class FailingDocumentImporter:
    def __init__(self, fail_on: set[str] | None = None) -> None:
        self.fail_on = fail_on or set()

    def import_document(self, document: WorkspaceDocument) -> int:
        if document.file_id in self.fail_on or not self.fail_on:
            raise DocumentImportError(
                "import failed",
                stage="download",
            )
        return 1


class BuggyDocumentImporter:
    def import_document(self, document: WorkspaceDocument) -> None:
        raise RuntimeError("unexpected importer bug")


class AddedOnlyWorkspaceScanner:
    def list_documents(self) -> list[WorkspaceDocument]:
        return [workspace_doc("added", "1")]


class EmptyQdrantIndex:
    def list_documents(self) -> list[QdrantDocument]:
        return []

    def delete_document(self, file_id: str) -> None:
        raise AssertionError(f"unexpected delete for file_id={file_id}")


class PipelineDownloader:
    def download(self, file_id, name, mime_type, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / name
        output_path.write_text("source", encoding="utf-8")
        return output_path


class PipelineTypeErrorConverter:
    def convert_to_pdf(self, source_path, mime_type, output_dir):
        raise TypeError("converter bug")


class PipelineDomainErrorConverter:
    def convert_to_pdf(self, source_path, mime_type, output_dir):
        raise DocumentConversionError("office conversion failed")


class PipelineRenderer:
    def render_pages(self, pdf_path, output_dir):
        return [PageImage(page_number=1, path=output_dir / "0001.png")]


class PipelineEmbedder:
    def embed_page_image(self, image_path):
        return [1.0, 0.0]


class PipelineQdrantIndex:
    def upsert_page_vectors(self, pages):
        return len(pages)


class OrchestratorTests(unittest.TestCase):
    def test_completed_document_info_includes_page_count_and_elapsed_time(self):
        logger = Mock(spec=logging.Logger)
        importer = Mock()
        importer.import_document.return_value = 3
        orchestrator = SyncOrchestrator(
            AddedOnlyWorkspaceScanner(), EmptyQdrantIndex(), importer, logger,
        )
        with patch("kbsearch_importer.orchestrator.monotonic", side_effect=[10, 14.5]):
            summary = orchestrator.run()
        completed = [call for call in logger.info.call_args_list if "action=%s status=success" in call.args[0]]
        self.assertEqual(len(completed), 1)
        self.assertIn("page_count=%s elapsed_seconds=%.2f", completed[0].args[0])
        self.assertEqual(completed[0].args[-2:], (3, 4.5))
        self.assertEqual(summary.imported, 1)

    def test_run_executes_import_delete_reimport_and_skip_actions(self) -> None:
        qdrant_index = FakeQdrantIndex()
        document_importer = FakeDocumentImporter()
        orchestrator = SyncOrchestrator(
            workspace_scanner=FakeWorkspaceScanner(),
            qdrant_index=qdrant_index,
            document_importer=document_importer,
        )

        summary = orchestrator.run()

        self.assertEqual(qdrant_index.deleted, ["changed", "deleted"])
        self.assertEqual(document_importer.imported, ["added", "changed"])
        self.assertEqual(summary.imported, 1)
        self.assertEqual(summary.deleted, 1)
        self.assertEqual(summary.reimported, 1)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(summary.failed, 0)

    def test_run_logs_batch_and_document_status(self) -> None:
        stream = StringIO()
        logger = logging.getLogger("kbsearch_importer.tests.orchestrator")
        logger.handlers = [logging.StreamHandler(stream)]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        orchestrator = SyncOrchestrator(
            workspace_scanner=FakeWorkspaceScanner(),
            qdrant_index=FakeQdrantIndex(),
            document_importer=FakeDocumentImporter(),
            logger=logger,
        )

        orchestrator.run()

        logs = stream.getvalue()
        self.assertIn("sync batch started", logs)
        self.assertIn("workspace_documents=", logs)
        self.assertIn("file_id=added name=added.pdf action=import status=success", logs)
        self.assertIn("sync batch finished", logs)

    def test_run_continues_after_failed_import_and_logs_summary(self) -> None:
        stream = StringIO()
        logger = logging.getLogger("kbsearch_importer.tests.orchestrator.failures")
        logger.handlers = [logging.StreamHandler(stream)]
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        orchestrator = SyncOrchestrator(
            workspace_scanner=FakeWorkspaceScanner(),
            qdrant_index=FakeQdrantIndex(),
            document_importer=FailingDocumentImporter(fail_on={"added", "changed"}),
            logger=logger,
        )

        summary = orchestrator.run()

        self.assertEqual(summary.imported, 0)
        self.assertEqual(summary.reimported, 0)
        self.assertEqual(summary.failed, 2)
        self.assertEqual(len(summary.failed_imports), 2)
        self.assertEqual(summary.failed_imports[0].file_id, "added")
        self.assertEqual(summary.failed_imports[0].action, "import")
        self.assertEqual(summary.failed_imports[0].stage, "download")
        self.assertEqual(summary.failed_imports[1].file_id, "changed")
        self.assertEqual(summary.failed_imports[1].action, "reimport")

        logs = stream.getvalue()
        self.assertIn("file_id=added name=added.pdf action=import stage=download page=- status=failed", logs)
        self.assertIn("sync batch failed imports summary count=2", logs)
        self.assertIn("sync batch failed import index=1 file_id=added", logs)
        self.assertIn("sync batch failed import index=2 file_id=changed", logs)
        self.assertIn("sync batch finished imported=0 deleted=1 reimported=0 skipped=1 failed=2", logs)

    def test_run_does_not_mark_failed_import_as_success(self) -> None:
        logger = logging.getLogger("kbsearch_importer.tests.orchestrator.silent")
        logger.handlers = [logging.NullHandler()]
        logger.propagate = False
        orchestrator = SyncOrchestrator(
            workspace_scanner=FakeWorkspaceScanner(),
            qdrant_index=FakeQdrantIndex(),
            document_importer=FailingDocumentImporter(),
            logger=logger,
        )

        summary = orchestrator.run()

        self.assertEqual(summary.failed, 2)
        self.assertEqual(summary.imported, 0)
        self.assertEqual(summary.reimported, 0)

    def test_run_aborts_batch_on_unexpected_importer_error(self) -> None:
        qdrant_index = FakeQdrantIndex()
        orchestrator = SyncOrchestrator(
            workspace_scanner=FakeWorkspaceScanner(),
            qdrant_index=qdrant_index,
            document_importer=BuggyDocumentImporter(),
            logger=logging.getLogger("kbsearch_importer.tests.orchestrator.abort"),
        )

        with self.assertRaises(RuntimeError):
            orchestrator.run()

        self.assertEqual(qdrant_index.deleted, [])

    def test_run_aborts_batch_when_pipeline_converter_raises_type_error(self) -> None:
        with TemporaryDirectory() as temp_dir:
            pipeline_importer = PipelineDocumentImporter(
                downloader=PipelineDownloader(),
                converter=PipelineTypeErrorConverter(),
                renderer=PipelineRenderer(),
                embedder=PipelineEmbedder(),
                qdrant_index=PipelineQdrantIndex(),
                work_dir=Path(temp_dir),
            )
            orchestrator = SyncOrchestrator(
                workspace_scanner=AddedOnlyWorkspaceScanner(),
                qdrant_index=EmptyQdrantIndex(),
                document_importer=pipeline_importer,
                logger=logging.getLogger("kbsearch_importer.tests.orchestrator.pipeline.abort"),
            )

            with self.assertRaises(TypeError):
                orchestrator.run()

    def test_run_continues_after_pipeline_domain_conversion_failure(self) -> None:
        with TemporaryDirectory() as temp_dir:
            pipeline_importer = PipelineDocumentImporter(
                downloader=PipelineDownloader(),
                converter=PipelineDomainErrorConverter(),
                renderer=PipelineRenderer(),
                embedder=PipelineEmbedder(),
                qdrant_index=PipelineQdrantIndex(),
                work_dir=Path(temp_dir),
            )
            orchestrator = SyncOrchestrator(
                workspace_scanner=AddedOnlyWorkspaceScanner(),
                qdrant_index=EmptyQdrantIndex(),
                document_importer=pipeline_importer,
                logger=logging.getLogger("kbsearch_importer.tests.orchestrator.pipeline.domain"),
            )

            summary = orchestrator.run()

        self.assertEqual(summary.imported, 0)
        self.assertEqual(summary.failed, 1)
        self.assertEqual(summary.failed_imports[0].stage, "convert")
        self.assertEqual(summary.failed_imports[0].error_type, "DocumentConversionError")


if __name__ == "__main__":
    unittest.main()
