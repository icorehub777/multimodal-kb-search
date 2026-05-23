"""
Qdrant Cloud 端到端串接測試：連線、匯入、查詢、刪除。

執行前請複製 .env.example 為 .env，並填入 QDRANT_API_KEY。

用法：
    python test_qdrant.py
"""

from __future__ import annotations

import sys

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

TEST_FILE_ID = "kbsearch-test-file-001"


def _unit_vector(dim: int, peak_index: int) -> list[float]:
    vec = [0.0] * dim
    vec[peak_index % dim] = 1.0
    return vec


def main() -> int:
    if not is_configured():
        print(
            "略過：請設定 .env 中的 QDRANT_URL、QDRANT_API_KEY，"
            "且勿將 QDRANT_SKIP 設為 1。",
            file=sys.stderr,
        )
        return 2

    cfg = get_config()
    dim = cfg["vector_size"]
    collection = cfg["collection"]

    print(f"連線至 {cfg['url']} …")
    client = get_client()

    try:
        collections = client.get_collections()
        names = [c.name for c in collections.collections]
        print(f"連線成功。目前 collections：{names or '(無)'}")

        setup_collection(client, collection, dim)
        print(f"使用 collection：{collection}")

        # 先清掉可能殘留的測試資料
        delete_by_google_file_id(client, collection, TEST_FILE_ID)

        pages = [
            (
                _unit_vector(dim, 0),
                page_payload(
                    google_file_id=TEST_FILE_ID,
                    file_name="串接測試.pdf",
                    file_path="/測試/串接測試.pdf",
                    file_link="https://drive.google.com/file/d/test/view",
                    drive_version="v1",
                    modified_time="2026-05-23T00:00:00Z",
                    page_number=1,
                    page_image_path="pages/test/01.png",
                    source_file_path="sources/test.pdf",
                ),
            ),
            (
                _unit_vector(dim, 1),
                page_payload(
                    google_file_id=TEST_FILE_ID,
                    file_name="串接測試.pdf",
                    file_path="/測試/串接測試.pdf",
                    file_link="https://drive.google.com/file/d/test/view",
                    drive_version="v1",
                    modified_time="2026-05-23T00:00:00Z",
                    page_number=2,
                    page_image_path="pages/test/02.png",
                    source_file_path="sources/test.pdf",
                ),
            ),
        ]

        n = upsert_pages(client, collection, pages)
        print(f"匯入完成：{n} 筆分頁向量")

        hits = search_similar(
            client,
            collection,
            _unit_vector(dim, 0),
            limit=3,
        )
        print(f"查詢完成：命中 {len(hits)} 筆")
        for hit in hits:
            payload = hit.payload or {}
            print(
                f"  score={hit.score:.4f} "
                f"file={payload.get('file_name')} "
                f"page={payload.get('page_number')}"
            )

        if not hits:
            print("查詢未命中任何資料。", file=sys.stderr)
            return 1

        top = hits[0].payload or {}
        if top.get("google_file_id") != TEST_FILE_ID:
            print("查詢結果不符合預期。", file=sys.stderr)
            return 1

        delete_by_google_file_id(client, collection, TEST_FILE_ID)
        remaining = count_by_google_file_id(client, collection, TEST_FILE_ID)
        print(f"刪除完成：檔案 {TEST_FILE_ID} 剩餘 {remaining} 筆")

        if remaining != 0:
            print("刪除後仍有殘留資料。", file=sys.stderr)
            return 1

        print("全部通過：連線、匯入、查詢、刪除皆正常。")
        return 0
    except Exception as exc:
        print(f"發生錯誤：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
