from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from app.domain import CollectedMetadata, MetadataCollectionError, PageMetadata


class MetadataCollector:
    def __init__(self, timeout_seconds: float, verify_ssl: bool = True, ca_bundle_path: str | None = None) -> None:
        verify = ca_bundle_path if ca_bundle_path is not None else verify_ssl
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "cloudsek-metadata-service/1.0"},
            verify=verify,
        )

    async def collect(self, url: str) -> CollectedMetadata:
        try:
            response = await self._client.get(url)
        except httpx.HTTPError as exc:
            raise MetadataCollectionError(str(exc)) from exc

        content_type = response.headers.get("content-type", "")
        is_html = "text/html" in content_type.lower()
        soup = BeautifulSoup(response.text, "html.parser") if is_html else None
        title = None
        description = None
        language = None
        links_count = None

        if soup is not None:
            if soup.title and soup.title.string:
                title = soup.title.string.strip() or None
            description_tag = soup.find("meta", attrs={"name": "description"})
            if description_tag is not None:
                description = description_tag.get("content")
            html_tag = soup.find("html")
            if html_tag is not None:
                language = html_tag.get("lang")
            links_count = len(soup.find_all("a", href=True))

        return CollectedMetadata(
            final_url=str(response.url),
            source="remote_http",
            http_status_code=response.status_code,
            headers={key: value for key, value in response.headers.items()},
            cookies={key: value for key, value in response.cookies.items()},
            page_source=response.text,
            page=PageMetadata(
                title=title,
                description=description,
                language=language,
                content_type=content_type or None,
                content_length=len(response.content),
                links_count=links_count,
            ),
        )

    async def close(self) -> None:
        await self._client.aclose()
