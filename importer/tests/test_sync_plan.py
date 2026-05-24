import unittest

from kbsearch_importer.models import QdrantDocument, WorkspaceDocument
from kbsearch_importer.sync_plan import SyncAction, plan_sync


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


class SyncPlanTests(unittest.TestCase):
    def test_plan_sync_classifies_added_deleted_changed_and_unchanged_documents(self) -> None:
        decisions = plan_sync(
            workspace_documents=[
                workspace_doc("added", "1"),
                workspace_doc("changed", "2"),
                workspace_doc("same", "1"),
            ],
            qdrant_documents=[
                QdrantDocument(file_id="deleted", version="1"),
                QdrantDocument(file_id="changed", version="1"),
                QdrantDocument(file_id="same", version="1"),
            ],
        )

        actions = {decision.file_id: decision.action for decision in decisions}

        self.assertEqual(actions["added"], SyncAction.IMPORT)
        self.assertEqual(actions["deleted"], SyncAction.DELETE)
        self.assertEqual(actions["changed"], SyncAction.REIMPORT)
        self.assertEqual(actions["same"], SyncAction.SKIP)


if __name__ == "__main__":
    unittest.main()
