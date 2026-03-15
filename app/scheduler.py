from __future__ import annotations

import asyncio

from app.domain import CollectionJob, MetadataCollectionError
from app.repositories import MetadataRepository


class BackgroundProcessor:
    def __init__(
        self,
        repository: MetadataRepository,
        collector: "MetadataCollector",
    ) -> None:
        self._repository = repository
        self._collector = collector
        self._queue: asyncio.Queue[CollectionJob | None] = asyncio.Queue()
        self._active_urls: set[str] = set()
        self._worker_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._worker_task is None:
            return
        await self._queue.put(None)
        await self._worker_task
        self._worker_task = None
        await self._collector.close()

    async def enqueue(self, job: CollectionJob) -> bool:
        if job.normalized_url in self._active_urls:
            return False
        self._active_urls.add(job.normalized_url)
        await self._queue.put(job)
        return True

    async def _run(self) -> None:
        while True:
            job = await self._queue.get()
            if job is None:
                self._queue.task_done()
                break
            try:
                await self._repository.mark_processing(job.normalized_url)
                metadata = await self._collector.collect(job.requested_url)
                await self._repository.mark_completed(job.normalized_url, metadata)
            except MetadataCollectionError as exc:
                await self._repository.mark_failed(
                    job.normalized_url,
                    exc.__class__.__name__,
                    str(exc),
                )
            except Exception as exc:
                await self._repository.mark_failed(
                    job.normalized_url,
                    exc.__class__.__name__,
                    "Unexpected metadata collection failure.",
                )
            finally:
                self._active_urls.discard(job.normalized_url)
                self._queue.task_done()
