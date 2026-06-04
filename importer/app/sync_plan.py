from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.models import QdrantDocument, WorkspaceDocument


class SyncAction(StrEnum):
    IMPORT = "import"
    DELETE = "delete"
    REIMPORT = "reimport"
    SKIP = "skip"


@dataclass(frozen=True)
class SyncDecision:
    file_id: str
    action: SyncAction
    workspace_document: WorkspaceDocument | None = None
    qdrant_document: QdrantDocument | None = None


def plan_sync(
    workspace_documents: list[WorkspaceDocument],
    qdrant_documents: list[QdrantDocument],
) -> list[SyncDecision]:
    workspace_by_id = {document.file_id: document for document in workspace_documents}
    qdrant_by_id = {document.file_id: document for document in qdrant_documents}

    decisions: list[SyncDecision] = []
    for file_id in sorted(set(workspace_by_id) | set(qdrant_by_id)):
        workspace_document = workspace_by_id.get(file_id)
        qdrant_document = qdrant_by_id.get(file_id)

        if workspace_document is not None and qdrant_document is None:
            decisions.append(
                SyncDecision(
                    file_id=file_id,
                    action=SyncAction.IMPORT,
                    workspace_document=workspace_document,
                )
            )
        elif workspace_document is None and qdrant_document is not None:
            decisions.append(
                SyncDecision(
                    file_id=file_id,
                    action=SyncAction.DELETE,
                    qdrant_document=qdrant_document,
                )
            )
        elif workspace_document is not None and qdrant_document is not None:
            if workspace_document.version != qdrant_document.version:
                decisions.append(
                    SyncDecision(
                        file_id=file_id,
                        action=SyncAction.REIMPORT,
                        workspace_document=workspace_document,
                        qdrant_document=qdrant_document,
                    )
                )
            else:
                decisions.append(
                    SyncDecision(
                        file_id=file_id,
                        action=SyncAction.SKIP,
                        workspace_document=workspace_document,
                        qdrant_document=qdrant_document,
                    )
                )

    return decisions
