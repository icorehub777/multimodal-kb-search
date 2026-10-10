"""One-shot Qdrant verification on the kbsearch Docker network."""

from __future__ import annotations

import os
import sys

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
COLLECTION = "kbsearch_local_verify"
VECTOR_SIZE = 64


def _run_importer_checks() -> tuple[list[float], str]:
    from kbsearch_importer.metadata import build_page_vector_metadata
    from kbsearch_importer.models import WorkspaceDocument
    from kbsearch_importer.qdrant_client_factory import build_qdrant_client
    from kbsearch_importer.qdrant_index import QdrantIndexAdapter, ensure_qdrant_collection

    client = build_qdrant_client(QDRANT_URL, None)
    ensure_qdrant_collection(client, COLLECTION, VECTOR_SIZE)
    index = QdrantIndexAdapter(client=client, collection=COLLECTION)

    probe_doc = WorkspaceDocument(
        file_id="kbsearch-local-verify",
        name="verify.pdf",
        location="/verify/verify.pdf",
        web_url="https://example.invalid/verify",
        version="v1",
        modified_time="2026-06-04T00:00:00Z",
        mime_type="application/pdf",
    )
    metadata = build_page_vector_metadata(document=probe_doc, page_number=1)
    vector = [1.0] + [0.0] * (VECTOR_SIZE - 1)

    print("importer.list_documents: start")
    print(f"importer.list_documents: ok count={len(index.list_documents())}")

    print("importer.upsert_page_vectors: start")
    print(f"importer.upsert_page_vectors: ok points={index.upsert_page_vectors([(vector, metadata)])}")

    listed = index.list_documents()
    if not any(doc.file_id == probe_doc.file_id for doc in listed):
        raise RuntimeError("list_documents did not return probe document")
    print("importer.list_documents after upsert: ok")

    return vector, probe_doc.file_id


def _run_secure_backend_checks(vector: list[float], expected_file_id: str) -> None:
    from kbsearch_backend.qdrant_client_factory import build_qdrant_client
    from kbsearch_backend.qdrant_search import QdrantSearchAdapter

    searcher = QdrantSearchAdapter(
        client=build_qdrant_client(QDRANT_URL, None),
        collection=COLLECTION,
    )
    print("secure_backend.search_pages: start")
    results = searcher.search_pages(vector=vector, limit=5, min_score=None)
    if not results or results[0].google_file_id != expected_file_id:
        raise RuntimeError("search_pages did not return probe document")
    print(
        "secure_backend.search_pages: ok "
        f"files={len(results)} pages={len(results[0].pages)}"
    )


def _cleanup_probe(file_id: str | None) -> None:
    from kbsearch_importer.qdrant_client_factory import build_qdrant_client
    from kbsearch_importer.qdrant_index import QdrantIndexAdapter

    client = build_qdrant_client(QDRANT_URL, None)
    if not client.collection_exists(COLLECTION):
        print("cleanup.delete_collection: skipped missing collection")
        return

    if file_id is not None:
        index = QdrantIndexAdapter(
            client=client,
            collection=COLLECTION,
        )
        print("importer.delete_document: start")
        index.delete_document(file_id)
        if any(doc.file_id == file_id for doc in index.list_documents()):
            raise RuntimeError("delete_document left probe document in index")
        print("importer.delete_document: ok")

    client.delete_collection(collection_name=COLLECTION)
    print("cleanup.delete_collection: ok")


def main() -> int:
    file_id = None
    try:
        vector, file_id = _run_importer_checks()
        _run_secure_backend_checks(vector, file_id)
    finally:
        _cleanup_probe(file_id)
    print("ALL_CHECKS_PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"VERIFY_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
