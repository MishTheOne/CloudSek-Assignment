from __future__ import annotations

import pytest

from app.domain import CollectedMetadata, CollectionJob, CollectionTrigger, MetadataStatus, PageMetadata
from app.repositories_memory import InMemoryMetadataRepository
from app.scheduler import BackgroundProcessor


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

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_background_processor_persists_collected_metadata():
    repository = InMemoryMetadataRepository()
    collector = FakeCollector()
    processor = BackgroundProcessor(repository, collector)

    await repository.create_or_refresh_submission(
        requested_url="https://example.com",
        normalized_url="https://example.com/",
        trigger=CollectionTrigger.GET,
    )
    await processor.start()
    await processor.enqueue(
        CollectionJob(
            requested_url="https://example.com",
            normalized_url="https://example.com/",
            trigger=CollectionTrigger.GET,
        )
    )
    await processor._queue.join()
    record = await repository.get_by_normalized_url("https://example.com/")

    assert record is not None
    assert record.status == MetadataStatus.COMPLETED
    assert record.page_source == "<html><body>Example Domain</body></html>"
    assert collector.calls == ["https://example.com"]

    await processor.stop()
