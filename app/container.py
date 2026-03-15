from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.config import Settings
from app.domain import CollectedMetadata, MetadataStorageError, PageMetadata
from app.repositories import MetadataRepository
from app.repositories_memory import InMemoryMetadataRepository
from app.scheduler import BackgroundProcessor
from app.services import Collector, JobScheduler, MetadataService


@dataclass(slots=True)
class Container:
    settings: Settings
    repository: MetadataRepository
    scheduler: JobScheduler
    service: MetadataService

    async def start(self) -> None:
        deadline = asyncio.get_running_loop().time() + self.settings.database_startup_timeout_seconds
        while True:
            try:
                await self.repository.create_indexes()
                break
            except MetadataStorageError:
                if asyncio.get_running_loop().time() >= deadline:
                    raise
                await asyncio.sleep(self.settings.database_retry_interval_seconds)
        if isinstance(self.scheduler, BackgroundProcessor):
            await self.scheduler.start()

    async def stop(self) -> None:
        if isinstance(self.scheduler, BackgroundProcessor):
            await self.scheduler.stop()
        await self.repository.close()


def build_container(settings: Settings | None = None) -> Container:
    effective_settings = settings or Settings.from_env()
    from motor.motor_asyncio import AsyncIOMotorClient

    from app.collector import MetadataCollector
    from app.repositories_mongo import MongoMetadataRepository

    client = AsyncIOMotorClient(effective_settings.mongodb_uri)
    repository = MongoMetadataRepository(
        client=client,
        database_name=effective_settings.database_name,
        collection_name=effective_settings.collection_name,
    )
    collector = MetadataCollector(
        effective_settings.request_timeout_seconds,
        verify_ssl=effective_settings.http_verify_ssl,
        ca_bundle_path=effective_settings.http_ca_bundle_path,
    )
    scheduler = BackgroundProcessor(repository, collector)
    service = MetadataService(repository, scheduler, collector)
    return Container(
        settings=effective_settings,
        repository=repository,
        scheduler=scheduler,
        service=service,
    )


class RecordingScheduler(JobScheduler):
    def __init__(self) -> None:
        self.jobs = []

    async def enqueue(self, job) -> bool:
        self.jobs.append(job)
        return True


class StubCollector(Collector):
    def __init__(self, metadata: CollectedMetadata | None = None) -> None:
        self.metadata = metadata or CollectedMetadata(
            final_url="https://example.com/",
            source="remote_http",
            http_status_code=200,
            headers={"content-type": "text/html"},
            cookies={},
            page_source="<html><body>Example Domain</body></html>",
            page=PageMetadata(
                title="Example Domain",
                description=None,
                language="en",
                content_type="text/html",
                content_length=41,
                links_count=1,
            ),
        )
        self.calls: list[str] = []

    async def collect(self, url: str) -> CollectedMetadata:
        self.calls.append(url)
        return self.metadata


def build_test_container(repository: MetadataRepository | None = None, collector: Collector | None = None) -> Container:
    effective_repository = repository or InMemoryMetadataRepository()
    effective_collector = collector or StubCollector()
    scheduler = RecordingScheduler()
    service = MetadataService(effective_repository, scheduler, effective_collector)
    return Container(
        settings=Settings.from_env(),
        repository=effective_repository,
        scheduler=scheduler,
        service=service,
    )
