from __future__ import annotations

from typing import Protocol

from app.domain import (
    CollectionJob,
    CollectionTrigger,
    CollectedMetadata,
    MetadataAcceptedResponse,
    MetadataCollectionError,
    MetadataRecord,
    MetadataStatus,
    normalize_url,
)
from app.repositories import MetadataRepository


class Collector(Protocol):
    async def collect(self, url: str) -> CollectedMetadata:
        ...


class MetadataService:
    def __init__(
        self,
        repository: MetadataRepository,
        scheduler: "JobScheduler",
        collector: Collector,
    ) -> None:
        self._repository = repository
        self._scheduler = scheduler
        self._collector = collector

    async def create_metadata(self, url: str) -> MetadataRecord:
        normalized_url = normalize_url(url)
        await self._repository.create_or_refresh_submission(url, normalized_url, CollectionTrigger.POST)
        await self._repository.mark_processing(normalized_url)
        try:
            metadata = await self._collector.collect(url)
        except MetadataCollectionError as exc:
            await self._repository.mark_failed(normalized_url, exc.__class__.__name__, str(exc))
            raise
        except Exception as exc:
            await self._repository.mark_failed(normalized_url, exc.__class__.__name__, "Unexpected metadata collection failure.")
            raise MetadataCollectionError("Unexpected metadata collection failure.") from exc

        stored_record = await self._repository.mark_completed(normalized_url, metadata)
        if stored_record is None:
            raise RuntimeError("Failed to persist collected metadata.")
        return stored_record

    async def get_metadata(self, url: str) -> MetadataRecord | MetadataAcceptedResponse:
        normalized_url = normalize_url(url)
        record = await self._repository.get_by_normalized_url(normalized_url)
        if record is None:
            return await self._queue_collection(url, normalized_url)
        if record.status == MetadataStatus.FAILED:
            return await self._queue_collection(url, normalized_url)
        if record.status in {MetadataStatus.QUEUED, MetadataStatus.PROCESSING}:
            return self._accepted_response(record)
        return record

    async def _queue_collection(self, url: str, normalized_url: str) -> MetadataAcceptedResponse:
        record = await self._repository.create_or_refresh_submission(url, normalized_url, CollectionTrigger.GET)
        await self._scheduler.enqueue(
            CollectionJob(
                requested_url=url,
                normalized_url=normalized_url,
                trigger=CollectionTrigger.GET,
            )
        )
        return self._accepted_response(record)

    @staticmethod
    def _accepted_response(record: MetadataRecord) -> MetadataAcceptedResponse:
        return MetadataAcceptedResponse(
            record_id=record.id,
            url=record.normalized_url,
            status=record.status,
            message="Metadata collection has been queued."
            if record.status == MetadataStatus.QUEUED
            else "Metadata collection is in progress.",
        )


class JobScheduler:
    async def enqueue(self, job: CollectionJob) -> bool:
        raise NotImplementedError
