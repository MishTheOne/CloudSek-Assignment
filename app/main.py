from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import register_exception_handlers, router
from app.container import Container, build_container


def create_app(container: Container | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        active_container = container or build_container()
        application.state.container = active_container
        await active_container.start()
        try:
            yield
        finally:
            await active_container.stop()

    application = FastAPI(
        title="CloudSEK Metadata Service",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.include_router(router)
    register_exception_handlers(application)
    return application


app = create_app()
