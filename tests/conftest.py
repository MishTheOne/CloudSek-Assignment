from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.container import Container, RecordingScheduler
from app.domain import CollectedMetadata, PageMetadata
from app.main import create_app
from app.repositories_memory import InMemoryMetadataRepository
from app.services import MetadataService


class FakeCollector:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.metadata = CollectedMetadata(
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

    async def collect(self, url: str) -> CollectedMetadata:
        self.calls.append(url)
        return self.metadata


@pytest.fixture()
def repository() -> InMemoryMetadataRepository:
    return InMemoryMetadataRepository()


@pytest.fixture()
def scheduler() -> RecordingScheduler:
    return RecordingScheduler()


@pytest.fixture()
def collector() -> FakeCollector:
    return FakeCollector()


@pytest.fixture()
def app(repository: InMemoryMetadataRepository, scheduler: RecordingScheduler, collector: FakeCollector):
    service = MetadataService(repository, scheduler, collector)
    container = Container(
        settings=Settings.from_env(),
        repository=repository,
        scheduler=scheduler,
        service=service,
    )
    return create_app(container)


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client
