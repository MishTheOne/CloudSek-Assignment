from __future__ import annotations

from copy import deepcopy

from app.domain import (
    CollectionError,
    CollectionTrigger,
    CollectedMetadata,
    MetadataRecord,
    MetadataStatus,
    new_record_id,
    utc_now,
)
from app.repositories import MetadataRepository


class InMemoryMetadataRepository(MetadataRepository):
    def __init__(self) -> None:
        self._records: dict[str, MetadataRecord] = {}

    async def create_indexes(self) -> None:
        return None

    async def get_by_normalized_url(self, normalized_url: str) -> MetadataRecord | None:
        record = self._records.get(normalized_url)
        return deepcopy(record) if record else None

    async def create_or_refresh_submission(
        self,
        requested_url: str,
        normalized_url: str,
        trigger: CollectionTrigger,
    ) -> MetadataRecord:
        now = utc_now()
        existing = self._records.get(normalized_url)
        if existing is None:
            record = MetadataRecord(
                id=new_record_id(),
                requested_url=requested_url,
                normalized_url=normalized_url,
                status=MetadataStatus.QUEUED,
                trigger=trigger,
                created_at=now,
                updated_at=now,
                last_requested_at=now,
            )
            self._records[normalized_url] = record
            return deepcopy(record)

        status = existing.status
        if status not in {MetadataStatus.QUEUED, MetadataStatus.PROCESSING}:
            status = MetadataStatus.QUEUED

        updated = existing.model_copy(
            update={
                "requested_url": requested_url,
                "trigger": trigger,
                "status": status,
                "error": None if status == MetadataStatus.QUEUED else existing.error,
                "updated_at": now,
                "last_requested_at": now,
            }
        )
        self._records[normalized_url] = updated
        return deepcopy(updated)

    async def mark_processing(self, normalized_url: str) -> MetadataRecord | None:
        record = self._records.get(normalized_url)
        if record is None:
            return None
        updated = record.model_copy(
            update={
                "status": MetadataStatus.PROCESSING,
                "error": None,
                "updated_at": utc_now(),
            }
        )
        self._records[normalized_url] = updated
        return deepcopy(updated)

    async def mark_completed(
        self,
        normalized_url: str,
        metadata: CollectedMetadata,
    ) -> MetadataRecord | None:
        record = self._records.get(normalized_url)
        if record is None:
            return None
        now = utc_now()
        updated = record.model_copy(
            update={
                "final_url": metadata.final_url,
                "status": MetadataStatus.COMPLETED,
                "source": metadata.source,
                "http_status_code": metadata.http_status_code,
                "headers": metadata.headers,
                "cookies": metadata.cookies,
                "page_source": metadata.page_source,
                "page": metadata.page,
                "error": None,
                "updated_at": now,
                "last_collected_at": now,
            }
        )
        self._records[normalized_url] = updated
        return deepcopy(updated)

    async def mark_failed(
        self,
        normalized_url: str,
        error_type: str,
        message: str,
    ) -> MetadataRecord | None:
        record = self._records.get(normalized_url)
        if record is None:
            return None
        now = utc_now()
        updated = record.model_copy(
            update={
                "status": MetadataStatus.FAILED,
                "error": CollectionError(type=error_type, message=message, occurred_at=now),
                "updated_at": now,
            }
        )
        self._records[normalized_url] = updated
        return deepcopy(updated)

    async def close(self) -> None:
        return None
