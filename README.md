# CloudSEK Metadata Service

This project implements the assignment as a FastAPI service backed by MongoDB with synchronous `POST` collection and asynchronous `GET` cache-miss recovery.

## Features

- `POST /metadata` accepts a URL, collects headers, cookies, and raw page source immediately, and stores the record in MongoDB.
- `GET /metadata?url=...` returns the stored dataset when present.
- `GET /metadata?url=...` returns `202 Accepted` and queues background collection when the record is missing.
- Background collection is handled internally without service-to-self HTTP calls.
- MongoDB lookups are indexed by normalized URL.
- FastAPI exposes interactive API documentation at `/docs`.

## Tech Stack

- Python 3.11
- FastAPI
- Motor
- MongoDB
- httpx
- Beautiful Soup
- pytest
- Docker Compose

## Run With Docker

```bash
docker-compose up
```

The stack starts:

- API at `http://localhost:8000`
- MongoDB at `mongodb://localhost:27017`

## Local Development

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Environment Variables

- `MONGODB_URI`
- `DATABASE_NAME`
- `COLLECTION_NAME`
- `REQUEST_TIMEOUT_SECONDS`
- `DATABASE_STARTUP_TIMEOUT_SECONDS`
- `DATABASE_RETRY_INTERVAL_SECONDS`
- `HTTP_VERIFY_SSL`
- `HTTP_CA_BUNDLE_PATH`

## TLS Notes

When the service collects metadata from external `https://` URLs, SSL verification is disabled by default so the stack works in restrictive local and corporate environments.

If you want strict SSL verification with a custom corporate root certificate, place the PEM file in `certs/` and start Docker with:

```bash
HTTP_CA_BUNDLE_PATH=/certs/your-root.pem docker-compose up --build
```

If you want to explicitly keep SSL verification disabled during collection, use:

```bash
HTTP_VERIFY_SSL=false docker-compose up --build
```

## API Summary

### POST `/metadata`

Request:

```json
{
  "url": "https://example.com"
}
```

Response:

```json
{
  "id": "b9f1c73e25c648dfb1ac2b2bf615e15f",
  "requested_url": "https://example.com",
  "normalized_url": "https://example.com/",
  "final_url": "https://example.com/",
  "status": "completed",
  "trigger": "post",
  "source": "remote_http",
  "http_status_code": 200,
  "headers": {
    "content-type": "text/html"
  },
  "cookies": {},
  "page_source": "<html>...</html>",
  "page": {
    "title": "Example Domain",
    "description": null,
    "language": "en",
    "content_type": "text/html",
    "content_length": 41,
    "links_count": 1
  },
  "error": null,
  "created_at": "2026-03-14T00:00:00Z",
  "updated_at": "2026-03-14T00:00:00Z",
  "last_requested_at": "2026-03-14T00:00:00Z",
  "last_collected_at": "2026-03-14T00:00:00Z"
}
```

### GET `/metadata?url=https://example.com`

- Returns `200` with the stored metadata when available.
- Returns `202` and queues background collection when the URL is not yet present or a prior async collection failed.

## Verification

This repository includes both automated unit tests and an end-to-end Docker Compose smoke test.

Local checks:

```bash
pytest
docker-compose up --build -d
docker-compose ps
curl http://localhost:8000/health
curl http://localhost:8000/docs
```

The GitHub Actions workflow in `.github/workflows/docker-compose-smoke.yml` boots the exact `docker-compose.yml`, waits for the API health endpoint, performs a `POST /metadata`, and validates the API response.

## Testing

Run the full pytest suite:

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
pytest
```

You can also run pytest directly through the virtual environment interpreter:

```bash
.venv\\Scripts\\python -m pytest
```

Run the Docker end-to-end smoke checks:

```bash
./start-stack.ps1 -Detach
./smoke-test.ps1
./stop-stack.ps1 -RemoveVolumes
```

If your network requires a custom CA bundle for outbound HTTPS collection, start the stack with:

```bash
./start-stack.ps1 -Detach -CaBundlePath /certs/your-root.pem
```

If you want to keep SSL verification disabled while testing:

```bash
./start-stack.ps1 -Detach -DisableSslVerification
```

The pytest suite covers API behavior, service logic, background scheduling, startup retry handling, and configuration parsing.

CI verification is provided by `.github/workflows/docker-compose-smoke.yml`, which runs the Docker Compose stack and validates the API from a clean environment.
