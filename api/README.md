# MISM Gateway API

Gateway REST API for MISM, built with FastAPI. It fronts internal microservices for search and uploads, and supports configurable bearer-token auth (only `oidc` currently).

## Prerequisites

- macOS Tahoe shell environment (zsh in Cursor terminal)
- Python 3.12
- `uv` package manager (`uv --version`)

## First-Time Setup

1. Copy environment template:

   ```bash
   cp .env.example .env
   ```

2. Install dependencies:

   ```bash
   make install
   ```

3. Update `.env` values for your local services:
   - `SEARCH_SERVICE_URL`
   - `UPLOAD_SERVICE_URL`
   - auth settings (`AUTH_MODE`)

4. Run the app:

   ```bash
   make dev
   ```

5. Open docs:
   - Swagger UI: `http://localhost:8000/docs`
   - Health check: `http://localhost:8000/healthz`

## Common Development Commands

- Install/update deps: `make install`
- Run local server: `make run`
- Run auto-reload server: `make dev`
- Run tests: `make test`
- Lint: `make lint`
- Format: `make format`
- Type check: `make typecheck`

## API Surface (Initial)

- `GET /api/v1/models`
  - Returns model search/discovery results from the search microservice.
  - Query params: `q`, `limit`, `offset`.
- `POST /api/v1/models`
- `PUT /api/v1/models`
  - Upserts model metadata.
  - `PUT` expects `model_id` in request JSON.
- `POST /api/v1/models/{modelId}/files`
  - Streams incoming file content for an existing model.
  - Uses chunked forwarding to upload microservice (`init`, `parts`, `complete`).
  - Retries transient errors by replaying a trailing in-memory part buffer.

## Authentication Modes

Set `AUTH_MODE` in `.env`:

- `AUTH_MODE=oidc`
  - Uses OIDC discovery and JWKS retrieval.
  - Configure `OIDC_ISSUER_URL` (or `OIDC_DISCOVERY_URL`) and `OIDC_AUDIENCE`.
  - Optionally enforce scopes with `OIDC_REQUIRED_SCOPES`.


## Upstream Service Stubbing

- `STUB_UPSTREAM_SERVICES=True` logs upstream actions and returns stubbed success payloads.
- `STUB_UPSTREAM_SERVICES=False` (default) enables real HTTP calls to `SEARCH_SERVICE_URL` / `UPLOAD_SERVICE_URL`.

## Logging

- Root logger is configured at startup.
- Every request is assigned/propagates `x-request-id`.
- Logs include request metadata for easier traceability across gateway and upstream services.

## Project Layout

```text
src/
  api/          # FastAPI routers
  auth/         # OIDC auth validators
  clients/      # Upstream service clients
  core/         # settings, errors, logging, service resolution
  middleware/   # request context middleware
  schemas/      # request/response models
  main.py       # FastAPI app entrypoint
tests/          # endpoint/auth tests
```
