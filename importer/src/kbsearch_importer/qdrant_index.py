from __future__ import annotations

import uuid
from typing import Any

from kbsearch_importer.models import PageVectorMetadata, QdrantDocument


class QdrantIndexAdapter:
    def __init__(self, client: Any, collection: str) -> None:
        self._client = client
        self._collection = collection

    def list_documents(self) -> list[QdrantDocument]:
        documents_by_id: dict[str, QdrantDocument] = {}
        offset = None
        while True:
            records, offset = self._client.scroll(
                collection_name=self._collection,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for record in records:
                payload = record.payload or {}
                file_id = payload.get("google_file_id")
                version = payload.get("google_drive_version")
                if file_id and version:
                    documents_by_id[str(file_id)] = QdrantDocument(
                        file_id=str(file_id),
                        version=str(version),
                    )
            if offset is None:
                return [documents_by_id[file_id] for file_id in sorted(documents_by_id)]

    def delete_document(self, file_id: str) -> None:
        self._client.delete(
            collection_name=self._collection,
            points_selector=_file_id_filter(file_id),
        )

    def upsert_page_vectors(
        self,
        pages: list[tuple[list[float] | tuple[float, ...], PageVectorMetadata]],
    ) -> int:
        points = [
            _point_struct(
                id=point_id(metadata.google_file_id, metadata.page_number),
                vector=list(vector),
                payload=metadata.to_payload(),
            )
            for vector, metadata in pages
        ]
        self._client.upsert(collection_name=self._collection, points=points)
        return len(points)


def point_id(google_file_id: str, page_number: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{google_file_id}:{page_number}"))


def _file_id_filter(file_id: str) -> Any:
    try:
        from qdrant_client.models import FieldCondition, Filter, MatchValue
    except ImportError:
        return {"must": [{"key": "google_file_id", "match": {"value": file_id}}]}
    return Filter(must=[FieldCondition(key="google_file_id", match=MatchValue(value=file_id))])


def _point_struct(id: str, vector: list[float], payload: dict[str, Any]) -> Any:
    try:
        from qdrant_client.models import PointStruct
    except ImportError:
        return {"id": id, "vector": vector, "payload": payload}
    return PointStruct(id=id, vector=vector, payload=payload)
