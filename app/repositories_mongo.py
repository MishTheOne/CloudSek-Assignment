from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from pymongo.errors import PyMongoError

from app.domain import (
    CollectionTrigger,
    CollectedMetadata,
    MetadataRecord,
    MetadataStatus,
    MetadataStorageError,
    new_record_id,
    record_from_document,
    utc_now,
)
from app.repositories import MetadataRepository


class MongoMetadataRepository(MetadataRepository):
    def __init__(
        self,
        client: AsyncIOMotorClient,
        database_name: str,
        collection_name: str,
    ) -> None:
        self._client = client
        self._collection: AsyncIOMotorCollection[dict[str, Any]] = client[database_name][collection_name]

    async def create_indexes(self) -> None:
        try:
            await self._collection.create_index("normalized_url", unique=True)
            await self._collection.create_index("status")
            await self._collection.create_index("last_requested_at")
        except PyMongoError as exc:
            raise MetadataStorageError("MongoDB is unavailable during startup initialization.") from exc

    async def get_by_normalized_url(self, normalized_url: str) -> MetadataRecord | None:
        try:
            document = await self._collection.find_one({"normalized_url": normalized_url})
        except PyMongoError as exc:
            raise MetadataStorageError("MongoDB lookup failed.") from exc
        return record_from_document(document) if document else None

    async def create_or_refresh_submission(
        self,
        requested_url: str,
        normalized_url: str,
        trigger: CollectionTrigger,
    ) -> MetadataRecord:
        now = utc_now()
        existing = await self.get_by_normalized_url(normalized_url)
        try:
            if existing is None:
                document = {
                    "_id": new_record_id(),
                    "requested_url": requested_url,
                    "normalized_url": normalized_url,
                    "final_url": None,
                    "status": MetadataStatus.QUEUED.value,
                    "trigger": trigger.value,
                    "source": None,
                    "http_status_code": None,
                    "headers": {},
                    "cookies": {},
                    "page_source": None,
                    "page": {},
                    "error": None,
                    "created_at": now,
                    "updated_at": now,
                    "last_requested_at": now,
                    "last_collected_at": None,
                }
                await self._collection.insert_one(document)
                return record_from_document(document)

            status = existing.status
            if status not in {MetadataStatus.QUEUED, MetadataStatus.PROCESSING}:
                status = MetadataStatus.QUEUED

            await self._collection.update_one(
                {"normalized_url": normalized_url},
                {
                    "$set": {
                        "requested_url": requested_url,
                        "status": status.value,
                        "trigger": trigger.value,
                        "error": None if status == MetadataStatus.QUEUED else existing.error.model_dump() if existing.error else None,
                        "updated_at": now,
                        "last_requested_at": now,
                    }
                },
            )
        except PyMongoError as exc:
            raise MetadataStorageError("MongoDB write failed while creating or refreshing metadata.") from exc

        updated = await self.get_by_normalized_url(normalized_url)
        if updated is None:
            raise RuntimeError("Failed to load metadata record after submission refresh.")
        return updated

    async def mark_processing(self, normalized_url: str) -> MetadataRecord | None:
        now = utc_now()
        try:
            await self._collection.update_one(
                {"normalized_url": normalized_url},
                {
                    "$set": {
                        "status": MetadataStatus.PROCESSING.value,
                        "error": None,
                        "updated_at": now,
                    }
                },
            )
        except PyMongoError as exc:
            raise MetadataStorageError("MongoDB write failed while marking metadata as processing.") from exc
        return await self.get_by_normalized_url(normalized_url)

    async def mark_completed(
        self,
        normalized_url: str,
        metadata: CollectedMetadata,
    ) -> MetadataRecord | None:
        now = utc_now()
        try:
            await self._collection.update_one(
                {"normalized_url": normalized_url},
                {
                    "$set": {
                        "final_url": metadata.final_url,
                        "status": MetadataStatus.COMPLETED.value,
                        "source": metadata.source,
                        "http_status_code": metadata.http_status_code,
                        "headers": metadata.headers,
                        "cookies": metadata.cookies,
                        "page_source": metadata.page_source,
                        "page": metadata.page.model_dump(),
                        "error": None,
                        "updated_at": now,
                        "last_collected_at": now,
                    }
                },
            )
        except PyMongoError as exc:
            raise MetadataStorageError("MongoDB write failed while persisting collected metadata.") from exc
        return await self.get_by_normalized_url(normalized_url)

    async def mark_failed(
        self,
        normalized_url: str,
        error_type: str,
        message: str,
    ) -> MetadataRecord | None:
        now = utc_now()
        try:
            await self._collection.update_one(
                {"normalized_url": normalized_url},
                {
                    "$set": {
                        "status": MetadataStatus.FAILED.value,
                        "error": {
                            "type": error_type,
                            "message": message,
                            "occurred_at": now,
                        },
                        "updated_at": now,
                    }
                },
            )
        except PyMongoError as exc:
            raise MetadataStorageError("MongoDB write failed while recording metadata collection failure.") from exc
        return await self.get_by_normalized_url(normalized_url)

    async def close(self) -> None:
        self._client.close()
