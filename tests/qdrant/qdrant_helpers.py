"""
Qdrant Cloud 串接輔助（匯入、依檔案刪除、向量查詢）。

對應設計規格中的每頁 metadata 欄位，供 indexer 與測試重用。
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    ScoredPoint,
    VectorParams,
)

# 依 google_file_id 刪除／scroll 時，Qdrant Cloud 需建立 keyword index
PAYLOAD_KEYWORD_FIELDS = ("google_file_id",)

_ENV_LOADED = False


def _load_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    from pathlib import Path

    load_dotenv(Path(__file__).resolve().parent / ".env")
    _ENV_LOADED = True


def get_config() -> dict[str, Any]:
    """讀取環境變數設定。"""
    _load_env()
    return {
        "url": os.environ.get("QDRANT_URL", "").strip(),
        "api_key": os.environ.get("QDRANT_API_KEY", "").strip(),
        "collection": os.environ.get(
            "QDRANT_COLLECTION", "kbsearch_integration_test"
        ).strip(),
        "vector_size": int(os.environ.get("QDRANT_VECTOR_SIZE", "2560")),
        "skip": os.environ.get("QDRANT_SKIP", "").strip() in ("1", "true", "yes"),
    }


def is_configured() -> bool:
    cfg = get_config()
    if cfg["skip"]:
        return False
    return bool(cfg["url"] and cfg["api_key"])


def get_client() -> QdrantClient:
    """建立 Qdrant Cloud 用戶端。"""
    cfg = get_config()
    if not cfg["url"]:
        raise RuntimeError("未設定 QDRANT_URL")
    if not cfg["api_key"]:
        raise RuntimeError("未設定 QDRANT_API_KEY（請於 .env 填入 Qdrant Cloud API Key）")
    return QdrantClient(url=cfg["url"], api_key=cfg["api_key"])


def point_id(google_file_id: str, page_number: int) -> str:
    """同一檔案同一頁的穩定 point ID。"""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{google_file_id}:{page_number}"))


def page_payload(
    *,
    google_file_id: str,
    file_name: str,
    file_path: str,
    file_link: str,
    drive_version: str,
    modified_time: str,
    page_number: int,
    page_image_path: str,
    source_file_path: str,
) -> dict[str, Any]:
    """組裝與設計規格對齊的 payload。"""
    return {
        "google_file_id": google_file_id,
        "file_name": file_name,
        "file_path": file_path,
        "file_link": file_link,
        "drive_version": drive_version,
        "modified_time": modified_time,
        "page_number": page_number,
        "page_image_path": page_image_path,
        "source_file_path": source_file_path,
    }


def ensure_collection(client: QdrantClient, collection: str, vector_size: int) -> None:
    """若 collection 不存在則建立（Cosine）。"""
    if client.collection_exists(collection):
        return
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def ensure_payload_indexes(client: QdrantClient, collection: str) -> None:
    """建立 payload 索引（刪除、依檔案篩選所需）。"""
    for field in PAYLOAD_KEYWORD_FIELDS:
        try:
            client.create_payload_index(
                collection_name=collection,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
                wait=True,
            )
        except Exception:
            # 索引已存在時略過
            pass


def setup_collection(client: QdrantClient, collection: str, vector_size: int) -> None:
    """確保 collection 與必要 payload 索引就緒。"""
    ensure_collection(client, collection, vector_size)
    ensure_payload_indexes(client, collection)


def upsert_pages(
    client: QdrantClient,
    collection: str,
    pages: list[tuple[list[float], dict[str, Any]]],
) -> int:
    """
    匯入多筆分頁向量。

    pages: [(vector, payload), ...]
    回傳寫入筆數。
    """
    points = [
        PointStruct(
            id=point_id(
                payload["google_file_id"],
                int(payload["page_number"]),
            ),
            vector=vector,
            payload=payload,
        )
        for vector, payload in pages
    ]
    client.upsert(collection_name=collection, points=points)
    return len(points)


def delete_by_google_file_id(
    client: QdrantClient,
    collection: str,
    google_file_id: str,
) -> None:
    """刪除某 Google 檔案在向量庫中的全部分頁。"""
    client.delete(
        collection_name=collection,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="google_file_id",
                    match=MatchValue(value=google_file_id),
                )
            ]
        ),
    )


def search_similar(
    client: QdrantClient,
    collection: str,
    query_vector: list[float],
    *,
    limit: int = 5,
    score_threshold: float | None = None,
) -> list[ScoredPoint]:
    """向量相似度查詢。"""
    response = client.query_points(
        collection_name=collection,
        query=query_vector,
        limit=limit,
        score_threshold=score_threshold,
    )
    return list(response.points)


def count_by_google_file_id(
    client: QdrantClient,
    collection: str,
    google_file_id: str,
) -> int:
    """計算某檔案在 collection 中的 point 數（測試用）。"""
    records, _ = client.scroll(
        collection_name=collection,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="google_file_id",
                    match=MatchValue(value=google_file_id),
                )
            ]
        ),
        limit=100,
        with_payload=False,
        with_vectors=False,
    )
    return len(records)
