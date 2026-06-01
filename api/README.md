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
   - auth settings, if auth is enabled (`OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_AUDIENCE`, `OIDC_REDIRECT_URI`)

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
- Run all tests: `make test`
- Run only unit tests: `make test-unit`
- Run only integration tests: `make test-integration`
- Run both unit and integration tests (what you can run without a live app run): `make test-ci`
- Lint: `make lint`
- Format: `make format`
- Type check: `make typecheck`

## API Surface

All API + auto-docs are mounted under `API_PATH_PREFIX` (default `/api`) so a
UI can serve at `/`. Swagger UI at `{prefix}/docs`, ReDoc at `{prefix}/redoc`.

- `GET /api/v1/models` — list models (filters: `name`, `owner`, `tags`,
  `organisms`, `scales`, `limit`, `offset`).
- `POST /api/v1/models` — register a model.
- `PUT /api/v1/models/{model_id}` — metadata corrections (immutable
  versioning is handled in the registry layer).
- `POST /api/v1/models/{model_id}/runs` — create a Run **and** trigger
  execution on the Execution API (mode: `batch` or `interactive`).
- `GET  /api/v1/models/{model_id}/runs` — all runs for a model with hydrated
  input/output resources, optional `?status=` filter.
- `GET  /api/v1/runs/{run_id}` — single run, optionally refreshing live status
  via the Execution API (`?refresh=false` skips the round-trip).
- `DELETE /api/v1/runs/{run_id}` — proxy DELETE to the Execution service to
  cancel; returns the post-cancel run shape.
- `GET  /api/v1/datasets`, `POST /api/v1/datasets`, `PUT /api/v1/datasets/{id}`.
- `POST /api/v1/resources/{resource_id}/files` — upload an artifact file for
  any registry resource (model, dataset, tool). Backend selected by
  `UPLOAD_BACKEND` (`local` writes to the iRODS PVC; `http` forwards to the
  upload service).
- `GET  /api/v1/resources/{resource_id}/files` — list artifacts.
- `GET  /api/v1/resources/{resource_id}/download` — download (whole-dir zip
  by default; single file via `?file=relpath`).
- `POST /api/v1/search` — full-text search with filters and aggregations
  (Postgres backend only).
- `GET  /api/auth/login`, `GET /api/auth/callback`, `POST /api/auth/logout`
  — OIDC authentication routes.

## Authentication Modes

Set `AUTH_MODE` in `.env`:

- `AUTH_MODE=oidc`
  - Uses OIDC discovery and JWKS retrieval.
  - Configure `OIDC_ISSUER_URL` (or `OIDC_DISCOVERY_URL`) and `OIDC_AUDIENCE`.
  - Optionally enforce scopes with `OIDC_REQUIRED_SCOPES`.

### Local development without an OIDC provider

Every `/api/v1/*` route is guarded by `require_principal`. When you are
working on a feature locally and don't have an OIDC issuer at hand:

```bash
# .env
DISABLE_AUTH=true
```

`DISABLE_AUTH=true` short-circuits `require_principal` to a synthetic
`anonymous` principal and skips OIDC discovery on startup. Do **not** set this
in any deployed environment.

If `DISABLE_AUTH=false` (the default) and you intend to run locally, you must
populate every `OIDC_*` setting that `core/config_validation.py` checks at
startup — `OIDC_ISSUER_URL`, `OIDC_AUDIENCE`, `OIDC_CLIENT_ID`,
`OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI`, `OIDC_COOKIE_SIGNING_SECRET`.


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
