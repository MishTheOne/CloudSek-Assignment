from __future__ import annotations

import os
from dataclasses import dataclass


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value: {value}")


@dataclass(slots=True)
class Settings:
    mongodb_uri: str
    database_name: str
    collection_name: str
    request_timeout_seconds: float
    database_startup_timeout_seconds: float
    database_retry_interval_seconds: float
    http_verify_ssl: bool
    http_ca_bundle_path: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        ca_bundle_path = os.getenv("HTTP_CA_BUNDLE_PATH")
        return cls(
            mongodb_uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
            database_name=os.getenv("DATABASE_NAME", "cloudsek"),
            collection_name=os.getenv("COLLECTION_NAME", "metadata_inventory"),
            request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "15")),
            database_startup_timeout_seconds=float(os.getenv("DATABASE_STARTUP_TIMEOUT_SECONDS", "30")),
            database_retry_interval_seconds=float(os.getenv("DATABASE_RETRY_INTERVAL_SECONDS", "2")),
            http_verify_ssl=parse_bool(os.getenv("HTTP_VERIFY_SSL", "false")),
            http_ca_bundle_path=ca_bundle_path.strip() if ca_bundle_path and ca_bundle_path.strip() else None,
        )
