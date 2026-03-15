from __future__ import annotations

from typing import Protocol

from app.domain import CollectionTrigger, CollectedMetadata, MetadataRecord


class MetadataRepository(Protocol):
    async def create_indexes(self) -> None:
        ...

    async def get_by_normalized_url(self, normalized_url: str) -> MetadataRecord | None:
        ...

    async def create_or_refresh_submission(
        self,
        requested_url: str,
        normalized_url: str,
        trigger: CollectionTrigger,
    ) -> MetadataRecord:
        ...

    async def mark_processing(self, normalized_url: str) -> MetadataRecord | None:
        ...

    async def mark_completed(
        self,
        normalized_url: str,
        metadata: CollectedMetadata,
    ) -> MetadataRecord | None:
        ...

    async def mark_failed(
        self,
        normalized_url: str,
        error_type: str,
        message: str,
    ) -> MetadataRecord | None:
        ...

    async def close(self) -> None:
        ...
