"""
pytest 串接測試：Qdrant Cloud 匯入、查詢、刪除。

未設定 QDRANT_API_KEY 或 QDRANT_SKIP=1 時自動略過。
"""

from __future__ import annotations

import pytest

from qdrant_helpers import (
    delete_by_google_file_id,
    setup_collection,
    get_client,
    get_config,
    is_configured,
    page_payload,
    search_similar,
    upsert_pages,
    count_by_google_file_id,
)

pytestmark = pytest.mark.skipif(
    not is_configured(),
    reason="未設定 Qdrant Cloud（QDRANT_URL + QDRANT_API_KEY），或已設 QDRANT_SKIP=1",
)

TEST_FILE_ID = "kbsearch-pytest-file-001"


@pytest.fixture(scope="module")
def qdrant_ctx():
    cfg = get_config()
    client = get_client()
    setup_collection(client, cfg["collection"], cfg["vector_size"])
    delete_by_google_file_id(client, cfg["collection"], TEST_FILE_ID)
    yield {"client": client, **cfg}
    delete_by_google_file_id(client, cfg["collection"], TEST_FILE_ID)


def _unit_vector(dim: int, peak_index: int) -> list[float]:
    vec = [0.0] * dim
    vec[peak_index % dim] = 1.0
    return vec


def test_connection_lists_collections(qdrant_ctx):
    client = qdrant_ctx["client"]
    result = client.get_collections()
    assert hasattr(result, "collections")


def test_upsert_query_delete_flow(qdrant_ctx):
    client = qdrant_ctx["client"]
    collection = qdrant_ctx["collection"]
    dim = qdrant_ctx["vector_size"]

    pages = [
        (
            _unit_vector(dim, 0),
            page_payload(
                google_file_id=TEST_FILE_ID,
                file_name="pytest.pdf",
                file_path="/pytest/doc.pdf",
                file_link="https://example.com/file",
                drive_version="v99",
                modified_time="2026-05-23T12:00:00Z",
                page_number=1,
                page_image_path="01.png",
                source_file_path="doc.pdf",
            ),
        ),
    ]
    assert upsert_pages(client, collection, pages) == 1

    hits = search_similar(client, collection, _unit_vector(dim, 0), limit=5)
    assert len(hits) >= 1
    assert hits[0].payload["google_file_id"] == TEST_FILE_ID

    delete_by_google_file_id(client, collection, TEST_FILE_ID)
    assert count_by_google_file_id(client, collection, TEST_FILE_ID) == 0
