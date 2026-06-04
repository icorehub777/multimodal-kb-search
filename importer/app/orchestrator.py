from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Protocol

from app.errors import ImporterError
from app.logging_config import LOGGER_NAME
from app.models import QdrantDocument, WorkspaceDocument
from app.sync_plan import SyncAction, plan_sync


class WorkspaceScanner(Protocol):
    def list_documents(self) -> list[WorkspaceDocument]:
        raise NotImplementedError


class QdrantIndex(Protocol):
    def list_documents(self) -> list[QdrantDocument]:
        raise NotImplementedError

    def delete_document(self, file_id: str) -> None:
        raise NotImplementedError


class DocumentImporter(Protocol):
    def import_document(self, document: WorkspaceDocument) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class SyncSummary:
    imported: int = 0
    deleted: int = 0
    reimported: int = 0
    skipped: int = 0


class SyncOrchestrator:
    def __init__(
        self,
        workspace_scanner: WorkspaceScanner,
        qdrant_index: QdrantIndex,
        document_importer: DocumentImporter,
        logger: logging.Logger | None = None,
    ) -> None:
        self._workspace_scanner = workspace_scanner
        self._qdrant_index = qdrant_index
        self._document_importer = document_importer
        self._logger = logger or logging.getLogger(LOGGER_NAME)

    def run(self) -> SyncSummary:
        workspace_documents = self._workspace_scanner.list_documents()
        qdrant_documents = self._qdrant_index.list_documents()
        decisions = plan_sync(
            workspace_documents=workspace_documents,
            qdrant_documents=qdrant_documents,
        )
        self._logger.info(
            "sync batch started workspace_documents=%s qdrant_documents=%s decisions=%s",
            len(workspace_documents),
            len(qdrant_documents),
            len(decisions),
        )

        imported = 0
        deleted = 0
        reimported = 0
        skipped = 0

        for decision in decisions:
            file_id = decision.file_id
            if decision.action == SyncAction.IMPORT:
                if decision.workspace_document is None:
                    raise ImporterError("Import decision missing workspace document.")
                document = decision.workspace_document
                self._run_import(document, "import")
                imported += 1
            elif decision.action == SyncAction.DELETE:
                self._qdrant_index.delete_document(file_id)
                self._logger.info("file_id=%s action=delete status=success", file_id)
                deleted += 1
            elif decision.action == SyncAction.REIMPORT:
                if decision.workspace_document is None:
                    raise ImporterError("Reimport decision missing workspace document.")
                document = decision.workspace_document
                self._qdrant_index.delete_document(file_id)
                self._logger.info(
                    "file_id=%s name=%s action=delete_before_reimport status=success",
                    file_id,
                    document.name,
                )
                self._run_import(document, "reimport")
                reimported += 1
            elif decision.action == SyncAction.SKIP:
                document = decision.workspace_document
                name = document.name if document is not None else ""
                self._logger.info(
                    "file_id=%s name=%s action=skip status=success",
                    file_id,
                    name,
                )
                skipped += 1

        summary = SyncSummary(
            imported=imported,
            deleted=deleted,
            reimported=reimported,
            skipped=skipped,
        )
        self._logger.info(
            "sync batch finished imported=%s deleted=%s reimported=%s skipped=%s",
            summary.imported,
            summary.deleted,
            summary.reimported,
            summary.skipped,
        )
        return summary

    def _run_import(self, document: WorkspaceDocument, action: str) -> None:
        try:
            self._document_importer.import_document(document)
        except Exception:
            self._logger.exception(
                "file_id=%s name=%s action=%s status=failed",
                document.file_id,
                document.name,
                action,
            )
            raise
        self._logger.info(
            "file_id=%s name=%s action=%s status=success",
            document.file_id,
            document.name,
            action,
        )
