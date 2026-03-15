from __future__ import annotations

import pytest

from app.config import Settings
from app.container import Container, RecordingScheduler
from app.domain import MetadataStorageError


class FlakyRepository:
    def __init__(self) -> None:
        self.attempts = 0

    async def create_indexes(self) -> None:
        self.attempts += 1
        if self.attempts < 3:
            raise MetadataStorageError("MongoDB is unavailable during startup initialization.")

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_container_start_retries_database_initialization():
    repository = FlakyRepository()
    settings = Settings(
        mongodb_uri="mongodb://localhost:27017",
        database_name="cloudsek",
        collection_name="metadata_inventory",
        request_timeout_seconds=15,
        database_startup_timeout_seconds=1,
        database_retry_interval_seconds=0.01,
        http_verify_ssl=True,
        http_ca_bundle_path=None,
    )
    container = Container(
        settings=settings,
        repository=repository,
        scheduler=RecordingScheduler(),
        service=None,
    )

    await container.start()

    assert repository.attempts == 3
