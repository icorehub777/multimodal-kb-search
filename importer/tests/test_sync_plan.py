import unittest

from app.models import QdrantDocument, WorkspaceDocument
from app.sync_plan import SyncAction, plan_sync


def workspace_doc(file_id: str, version: str, modified_time: str) -> WorkspaceDocument:
    return WorkspaceDocument(
        file_id=file_id,
        name=f"{file_id}.pdf",
        location=f"/source/{file_id}.pdf",
        web_url=f"https://drive.google.com/file/d/{file_id}",
        version=version,
        modified_time=modified_time,
        mime_type="application/pdf",
    )


class SyncPlanTests(unittest.TestCase):
    def test_plan_sync_classifies_added_deleted_changed_and_unchanged_documents(self) -> None:
        decisions = plan_sync(
            workspace_documents=[
                workspace_doc("added", "1", "2026-05-24T00:00:00Z"),
                workspace_doc("changed", "1", "2026-05-25T00:00:00Z"),
                workspace_doc("same", "9", "2026-05-24T00:00:00Z"),
            ],
            qdrant_documents=[
                QdrantDocument(file_id="deleted", modified_time="2026-05-24T00:00:00Z"),
                QdrantDocument(file_id="changed", modified_time="2026-05-24T00:00:00Z"),
                QdrantDocument(file_id="same", modified_time="2026-05-24T00:00:00Z"),
            ],
        )

        actions = {decision.file_id: decision.action for decision in decisions}

        self.assertEqual(actions["added"], SyncAction.IMPORT)
        self.assertEqual(actions["deleted"], SyncAction.DELETE)
        self.assertEqual(actions["changed"], SyncAction.REIMPORT)
        self.assertEqual(actions["same"], SyncAction.SKIP)


if __name__ == "__main__":
    unittest.main()
