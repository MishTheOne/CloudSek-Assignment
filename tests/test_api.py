from __future__ import annotations

from app.domain import CollectionTrigger, CollectedMetadata, MetadataStatus, PageMetadata


def test_post_metadata_collects_immediately_and_persists_data(client, scheduler, collector):
    response = client.post("/metadata", json={"url": "https://example.com"})

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == MetadataStatus.COMPLETED.value
    assert payload["page_source"] == "<html><body>Example Domain</body></html>"
    assert payload["headers"]["content-type"] == "text/html"
    assert len(scheduler.jobs) == 0
    assert collector.calls == ["https://example.com"]


def test_get_metadata_returns_accepted_and_queues_when_missing(client, scheduler, collector):
    response = client.get("/metadata", params={"url": "https://example.com"})

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == MetadataStatus.QUEUED.value
    assert len(scheduler.jobs) == 1
    assert scheduler.jobs[0].trigger == CollectionTrigger.GET
    assert collector.calls == []


async def test_get_metadata_returns_record_when_available(repository, client):
    record = await repository.create_or_refresh_submission(
        requested_url="https://example.com",
        normalized_url="https://example.com/",
        trigger=CollectionTrigger.POST,
    )
    await repository.mark_completed(
        record.normalized_url,
        CollectedMetadata(
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
                content_length=128,
                links_count=1,
            ),
        ),
    )

    response = client.get("/metadata", params={"url": "https://example.com"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == MetadataStatus.COMPLETED.value
    assert payload["page_source"] == "<html><body>Example Domain</body></html>"


def test_invalid_url_returns_bad_request(client):
    response = client.post("/metadata", json={"url": "ftp://example.com"})

    assert response.status_code == 400
    assert "http or https" in response.json()["detail"]
