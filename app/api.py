from __future__ import annotations

from fastapi import APIRouter, FastAPI, Query, Request, status
from fastapi.responses import JSONResponse

from app.container import Container
from app.domain import (
    ErrorResponse,
    InvalidUrlError,
    MetadataAcceptedResponse,
    MetadataCollectionError,
    MetadataRecord,
    MetadataRequest,
    MetadataStorageError,
)

router = APIRouter()


def get_container(request: Request) -> Container:
    return request.app.state.container


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/metadata",
    response_model=MetadataRecord,
    responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    status_code=status.HTTP_201_CREATED,
)
async def create_metadata(
    payload: MetadataRequest,
    request: Request,
) -> MetadataRecord:
    container = get_container(request)
    return await container.service.create_metadata(payload.url)


@router.get(
    "/metadata",
    response_model=MetadataRecord | MetadataAcceptedResponse,
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_metadata(
    request: Request,
    url: str = Query(...),
) -> MetadataRecord | JSONResponse:
    container = get_container(request)
    result = await container.service.get_metadata(url)
    if isinstance(result, MetadataAcceptedResponse):
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=result.model_dump(mode="json"),
        )
    return result


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidUrlError)
    async def invalid_url_handler(_: Request, exc: InvalidUrlError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(detail=str(exc)).model_dump(),
        )

    @app.exception_handler(MetadataCollectionError)
    async def metadata_collection_handler(_: Request, exc: MetadataCollectionError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=ErrorResponse(detail=str(exc)).model_dump(),
        )

    @app.exception_handler(MetadataStorageError)
    async def metadata_storage_handler(_: Request, exc: MetadataStorageError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(detail=str(exc)).model_dump(),
        )
