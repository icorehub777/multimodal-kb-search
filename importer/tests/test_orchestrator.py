import unittest
from io import StringIO
import logging

from app.errors import DocumentImportError
from app.models import QdrantDocument, WorkspaceDocument
from app.orchestrator import SyncOrchestrator


def workspace_doc(file_id: str, version: str) -> WorkspaceDocument:
    return WorkspaceDocument(
        file_id=file_id,
        name=f"{file_id}.pdf",
        location=f"/source/{file_id}.pdf",
        web_url=f"https://drive.google.com/file/d/{file_id}",
        version=version,
        modified_time="2026-05-24T00:00:00Z",
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
            QdrantDocument(file_id="deleted", version="1"),
            QdrantDocument(file_id="changed", version="1"),
            QdrantDocument(file_id="same", version="1"),
        ]
        self.deleted: list[str] = []

    def list_documents(self) -> list[QdrantDocument]:
        return self.documents

    def delete_document(self, file_id: str) -> None:
        self.deleted.append(file_id)


class FakeDocumentImporter:
    def __init__(self) -> None:
        self.imported: list[str] = []

    def import_document(self, document: WorkspaceDocument) -> None:
        self.imported.append(document.file_id)


class FailingDocumentImporter:
    def import_document(self, document: WorkspaceDocument) -> None:
        raise DocumentImportError("import failed")


class OrchestratorTests(unittest.TestCase):
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

    def test_run_logs_batch_and_document_status(self) -> None:
        stream = StringIO()
        logger = logging.getLogger("app.tests.orchestrator")
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

    def test_run_does_not_mark_failed_import_as_success(self) -> None:
        logger = logging.getLogger("app.tests.orchestrator.silent")
        logger.handlers = [logging.NullHandler()]
        logger.propagate = False
        orchestrator = SyncOrchestrator(
            workspace_scanner=FakeWorkspaceScanner(),
            qdrant_index=FakeQdrantIndex(),
            document_importer=FailingDocumentImporter(),
            logger=logger,
        )

        with self.assertRaises(DocumentImportError):
            orchestrator.run()


if __name__ == "__main__":
    unittest.main()
