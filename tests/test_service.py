from __future__ import annotations

import pytest

from app.container import RecordingScheduler
from app.domain import CollectedMetadata, CollectionTrigger, MetadataAcceptedResponse, MetadataStatus, PageMetadata, normalize_url
from app.repositories_memory import InMemoryMetadataRepository
from app.services import MetadataService


class FakeCollector:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def collect(self, url: str) -> CollectedMetadata:
        self.calls.append(url)
        return CollectedMetadata(
            final_url="https://example.com/",
            source="remote_http",
            http_status_code=200,
            headers={"content-type": "text/html"},
            cookies={"session": "value"},
            page_source="<html><body>Example Domain</body></html>",
            page=PageMetadata(
                title="Example Domain",
                description="Example",
                language="en",
                content_type="text/html",
                content_length=41,
                links_count=1,
            ),
        )


def test_normalize_url_keeps_query_and_standardizes_host():
    normalized = normalize_url(" HTTPS://Example.COM/path?q=1 ")

    assert normalized == "https://example.com/path?q=1"


@pytest.mark.asyncio
async def test_create_metadata_collects_without_scheduling():
    repository = InMemoryMetadataRepository()
    scheduler = RecordingScheduler()
    collector = FakeCollector()
    service = MetadataService(repository, scheduler, collector)

    result = await service.create_metadata("https://example.com")

    assert result.status == MetadataStatus.COMPLETED
    assert result.page_source == "<html><body>Example Domain</body></html>"
    assert collector.calls == ["https://example.com"]
    assert len(scheduler.jobs) == 0


@pytest.mark.asyncio
async def test_get_metadata_queues_background_job_when_missing():
    repository = InMemoryMetadataRepository()
    scheduler = RecordingScheduler()
    collector = FakeCollector()
    service = MetadataService(repository, scheduler, collector)

    result = await service.get_metadata("https://example.com")

    assert isinstance(result, MetadataAcceptedResponse)
    assert result.status == MetadataStatus.QUEUED
    assert len(scheduler.jobs) == 1
    assert scheduler.jobs[0].trigger == CollectionTrigger.GET
    assert collector.calls == []


@pytest.mark.asyncio
async def test_get_metadata_requeues_failed_record():
    repository = InMemoryMetadataRepository()
    scheduler = RecordingScheduler()
    collector = FakeCollector()
    service = MetadataService(repository, scheduler, collector)

    record = await repository.create_or_refresh_submission(
        requested_url="https://example.com",
        normalized_url="https://example.com/",
        trigger=CollectionTrigger.POST,
    )
    await repository.mark_failed(record.normalized_url, "TimeoutError", "Timed out")

    result = await service.get_metadata("https://example.com")

    assert isinstance(result, MetadataAcceptedResponse)
    assert result.status == MetadataStatus.QUEUED
    assert len(scheduler.jobs) == 1
