from __future__ import annotations

import uuid
from typing import Any

from kbsearch_importer.errors import ExternalServiceError
from kbsearch_importer.models import PageVectorMetadata, QdrantDocument


def ensure_qdrant_collection(client: Any, collection: str, vector_size: int) -> bool:
    """Create the Qdrant collection when missing and ensure payload indexes. Returns True if created."""
    created = False
    try:
        collection_exists = client.collection_exists(collection)
    except Exception as exc:
        raise ExternalServiceError(
            f"Qdrant collection lookup failed (collection={collection})."
        ) from exc
    if not collection_exists:
        try:
            from qdrant_client.models import Distance, VectorParams

            client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        except Exception as exc:
            raise ExternalServiceError(
                f"Qdrant create collection failed (collection={collection}, vector_size={vector_size})."
            ) from exc
        created = True

    ensure_google_file_id_payload_index(client, collection)
    return created


def ensure_google_file_id_payload_index(client: Any, collection: str) -> None:
    """Ensure keyword index on google_file_id for delete-by-file filters."""
    try:
        from qdrant_client.models import PayloadSchemaType

        client.create_payload_index(
            collection_name=collection,
            field_name="google_file_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
    except Exception as exc:
        message = str(exc).lower()
        if "already exists" in message or "already indexed" in message:
            return
        raise ExternalServiceError(
            f"Qdrant payload index creation failed (collection={collection}, field=google_file_id)."
        ) from exc


class QdrantIndexAdapter:
    def __init__(self, client: Any, collection: str) -> None:
        self._client = client
        self._collection = collection

    def list_documents(self) -> list[QdrantDocument]:
        documents_by_id: dict[str, QdrantDocument] = {}
        offset = None
        while True:
            try:
                records, offset = self._client.scroll(
                    collection_name=self._collection,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
            except Exception as exc:
                raise ExternalServiceError(
                    f"Qdrant document list failed (collection={self._collection})."
                ) from exc
            if not isinstance(records, (list, tuple)):
                raise ExternalServiceError(
                    f"Qdrant scroll returned an invalid response (collection={self._collection})."
                )
            for record in records:
                payload = getattr(record, "payload", None)
                if not isinstance(payload, dict):
                    raise ExternalServiceError(
                        f"Qdrant record has an invalid payload (collection={self._collection})."
                    )
                file_id = payload.get("google_file_id")
                modified_time = payload.get("google_drive_modified_time")
                if not file_id or not modified_time:
                    raise ExternalServiceError(
                        "Qdrant record is missing required payload "
                        f"(collection={self._collection}, fields=google_file_id,google_drive_modified_time)."
                    )
                normalized_id = str(file_id)
                normalized_time = str(modified_time)
                existing = documents_by_id.get(normalized_id)
                if existing is not None and existing.modified_time != normalized_time:
                    raise ExternalServiceError(
                        "Qdrant document has conflicting modified times "
                        f"(collection={self._collection}, file_id={normalized_id})."
                    )
                documents_by_id[normalized_id] = QdrantDocument(
                    file_id=normalized_id,
                    modified_time=normalized_time,
                )
            if offset is None:
                return [documents_by_id[file_id] for file_id in sorted(documents_by_id)]

    def delete_document(self, file_id: str) -> None:
        try:
            self._client.delete(
                collection_name=self._collection,
                points_selector=_file_id_filter(file_id),
            )
        except Exception as exc:
            raise ExternalServiceError(
                f"Qdrant document delete failed (collection={self._collection}, file_id={file_id})."
            ) from exc

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
        try:
            self._client.upsert(collection_name=self._collection, points=points)
        except Exception as exc:
            raise ExternalServiceError(
                f"Qdrant page vector upsert failed (collection={self._collection}, points={len(points)})."
            ) from exc
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
