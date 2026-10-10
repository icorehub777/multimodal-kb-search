from __future__ import annotations

from dataclasses import dataclass
import logging
from time import monotonic
from typing import Protocol

from kbsearch_importer.errors import DocumentImportError, DocumentImportFailure, ImporterError
from kbsearch_importer.logging_config import LOGGER_NAME
from kbsearch_importer.models import QdrantDocument, WorkspaceDocument
from kbsearch_importer.sync_plan import SyncAction, plan_sync


class WorkspaceScanner(Protocol):
    def list_documents(self) -> list[WorkspaceDocument]:
        raise NotImplementedError


class QdrantIndex(Protocol):
    def list_documents(self) -> list[QdrantDocument]:
        raise NotImplementedError

    def delete_document(self, file_id: str) -> None:
        raise NotImplementedError


class DocumentImporter(Protocol):
    def import_document(self, document: WorkspaceDocument) -> int:
        raise NotImplementedError


@dataclass(frozen=True)
class SyncSummary:
    imported: int = 0
    deleted: int = 0
    reimported: int = 0
    skipped: int = 0
    failed: int = 0
    failed_imports: tuple[DocumentImportFailure, ...] = ()


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
        failed_imports: list[DocumentImportFailure] = []

        for decision in decisions:
            file_id = decision.file_id
            if decision.action == SyncAction.IMPORT:
                if decision.workspace_document is None:
                    raise ImporterError("Import decision missing workspace document.")
                document = decision.workspace_document
                if self._run_import(document, "import", failed_imports):
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
                if self._run_import(document, "reimport", failed_imports):
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
            failed=len(failed_imports),
            failed_imports=tuple(failed_imports),
        )
        self._logger.info(
            "sync batch finished imported=%s deleted=%s reimported=%s skipped=%s failed=%s",
            summary.imported,
            summary.deleted,
            summary.reimported,
            summary.skipped,
            summary.failed,
        )
        self._log_failed_import_summary(summary.failed_imports)
        return summary

    def _run_import(
        self,
        document: WorkspaceDocument,
        action: str,
        failed_imports: list[DocumentImportFailure],
    ) -> bool:
        started_at = monotonic()
        try:
            page_count = self._document_importer.import_document(document)
        except DocumentImportError as exc:
            failure = _document_import_failure(document, action, exc)
            failed_imports.append(failure)
            self._logger.error(
                "file_id=%s name=%s action=%s stage=%s page=%s status=failed "
                "error_type=%s error_message=%s",
                failure.file_id,
                failure.name,
                failure.action,
                failure.stage,
                failure.page_number if failure.page_number is not None else "-",
                failure.error_type,
                failure.error_message,
            )
            return False
        self._logger.info(
            "file_id=%s name=%s action=%s status=success page_count=%s elapsed_seconds=%.2f",
            document.file_id,
            document.name,
            action,
            page_count,
            monotonic() - started_at,
        )
        return True

    def _log_failed_import_summary(
        self,
        failed_imports: tuple[DocumentImportFailure, ...],
    ) -> None:
        if not failed_imports:
            return
        self._logger.error(
            "sync batch failed imports summary count=%s",
            len(failed_imports),
        )
        for index, failure in enumerate(failed_imports, start=1):
            self._logger.error(
                "sync batch failed import index=%s file_id=%s name=%s action=%s stage=%s "
                "page=%s error_type=%s error_message=%s",
                index,
                failure.file_id,
                failure.name,
                failure.action,
                failure.stage,
                failure.page_number if failure.page_number is not None else "-",
                failure.error_type,
                failure.error_message,
            )


def _document_import_failure(
    document: WorkspaceDocument,
    action: str,
    exc: DocumentImportError,
) -> DocumentImportFailure:
    root_exc = exc.__cause__ if exc.__cause__ is not None else exc
    return DocumentImportFailure(
        file_id=document.file_id,
        name=document.name,
        action=action,
        stage=exc.stage,
        page_number=exc.page_number,
        error_type=root_exc.__class__.__name__,
        error_message=str(root_exc),
    )
