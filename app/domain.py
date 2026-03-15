from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from urllib.parse import ParseResult, urlparse, urlunparse
from uuid import uuid4

from pydantic import BaseModel, Field


class MetadataStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CollectionTrigger(str, Enum):
    POST = "post"
    GET = "get"


class MetadataRequest(BaseModel):
    url: str


class PageMetadata(BaseModel):
    title: str | None = None
    description: str | None = None
    language: str | None = None
    content_type: str | None = None
    content_length: int | None = None
    links_count: int | None = None


class CollectionError(BaseModel):
    type: str
    message: str
    occurred_at: datetime


class MetadataRecord(BaseModel):
    id: str
    requested_url: str
    normalized_url: str
    final_url: str | None = None
    status: MetadataStatus
    trigger: CollectionTrigger
    source: str | None = None
    http_status_code: int | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict)
    page_source: str | None = None
    page: PageMetadata = Field(default_factory=PageMetadata)
    error: CollectionError | None = None
    created_at: datetime
    updated_at: datetime
    last_requested_at: datetime
    last_collected_at: datetime | None = None


class MetadataAcceptedResponse(BaseModel):
    record_id: str
    url: str
    status: MetadataStatus
    message: str


class ErrorResponse(BaseModel):
    detail: str


class CollectedMetadata(BaseModel):
    final_url: str
    source: str
    http_status_code: int
    headers: dict[str, str]
    cookies: dict[str, str]
    page_source: str
    page: PageMetadata


@dataclass(slots=True)
class CollectionJob:
    requested_url: str
    normalized_url: str
    trigger: CollectionTrigger


class InvalidUrlError(ValueError):
    pass


class MetadataCollectionError(Exception):
    pass


class MetadataStorageError(Exception):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_record_id() -> str:
    return uuid4().hex


def normalize_url(value: str) -> str:
    candidate = value.strip()
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise InvalidUrlError("The provided URL must use http or https and include a host.")

    normalized = ParseResult(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=parsed.path or "/",
        params="",
        query=parsed.query,
        fragment="",
    )
    return urlunparse(normalized)


def record_from_document(document: dict[str, Any]) -> MetadataRecord:
    payload = dict(document)
    payload["id"] = payload.pop("_id")
    return MetadataRecord.model_validate(payload)
