"""Live OpenFGA integration check (MISM-291, Checkpoint E).

Unlike its sibling files in tests/functional/, this does NOT hit an
already-running `api` container over HTTP. It builds the app in-process via
create_app() instead, because exercising the real OpenFGA path requires a
principal whose issuer is not "local" (see
RegistryService._openfga_client_for) — and the `api` container in
docker-compose.test.yaml always runs with DISABLE_AUTH=true, which forces
issuer="local" for every request it handles, silently bypassing OpenFGA.
Dependency-override injection of a non-"local" principal (as
tests/unit/test_models_endpoint.py already does) is only possible against
an in-process app, not a separately-running container.

Requires, running before this file:
  - Postgres reachable, migrations applied:
      docker compose -f ../docker-compose.test.yaml up -d --build migrate
  - A local OpenFGA instance loaded with the mism-auth-model branch's schema
    (this file creates its own store + loads model.json itself, mirroring
    infra/helm-charts/OpenFGA/tests/conftest.py::store_and_model):
      cd ../../infra/helm-charts/OpenFGA && make functional-up

Redis is NOT required: DISABLE_AUTH=True means SessionMiddleware is never
registered and container.prime() returns immediately, and override_principal
replaces require_principal/optional_principal outright, so no code path in
this test ever touches the Redis-backed session store. AppContainer still
constructs a Redis client object (Redis.from_url doesn't connect eagerly),
so an unreachable REDIS_URL causes no error at build or teardown time.

Run:
    uv run pytest tests/functional/test_openfga_live.py -m integration -v
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.clients.openfga_client import OpenFGAClient
from mismapi.core.settings import Settings
from mismapi.main import create_app
from tests.conftest import TestSettings, override_principal
from tests.functional.helpers import unique_name

pytestmark = pytest.mark.integration

OPENFGA_BASE_URL = os.environ.get("OPENFGA_TEST_BASE_URL", "http://localhost:8080")
DATABASE_URL = os.environ.get(
    "MISM_TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5433/mism_test",
)

# infra is a sibling repo checked out next to model-discovery; override via
# env if your local layout differs.
MODEL_JSON_PATH = Path(
    os.environ.get(
        "MISM_AUTH_MODEL_JSON",
        str(
            Path(__file__).resolve().parents[4] / "infra" / "helm-charts" / "OpenFGA" / "model.json"
        ),
    )
)


def _wait_for_openfga(client: httpx.Client, timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if client.get("/healthz").status_code == 200:
                return
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"OpenFGA not healthy at {OPENFGA_BASE_URL}: {last_error!r}")


@pytest.fixture(scope="module")
def openfga_store_and_model() -> Generator[tuple[str, str], None, None]:
    """Create a fresh store, load mism-auth-model's model.json, yield (store_id, model_id)."""
    with httpx.Client(base_url=OPENFGA_BASE_URL, timeout=10) as client:
        _wait_for_openfga(client)

        store_name = f"mism-discovery-live-{uuid.uuid4().hex[:8]}"
        store_resp = client.post("/stores", json={"name": store_name})
        store_resp.raise_for_status()
        store_id = store_resp.json()["id"]

        model_definition = json.loads(MODEL_JSON_PATH.read_text())
        model_resp = client.post(f"/stores/{store_id}/authorization-models", json=model_definition)
        model_resp.raise_for_status()
        model_id = model_resp.json()["authorization_model_id"]

        yield store_id, model_id
        # Disposable in-memory OpenFGA instance — no per-store cleanup needed;
        # `make functional-down` (infra) tears the whole container down.


@pytest.fixture(scope="module")
def live_settings(openfga_store_and_model: tuple[str, str]) -> Settings:
    store_id, model_id = openfga_store_and_model
    return TestSettings(
        DISABLE_AUTH=True,  # override_principal replaces require_principal/
        # optional_principal outright, so the real issuer="local" path never
        # runs — OpenFGA calls are NOT bypassed despite this being True.
        DATABASE_URL=DATABASE_URL,
        REDIS_URL="redis://localhost:6379/15",  # never actually reached — see module docstring.
        TUSD_BASE_URL="http://tusd.test",
        OPENFGA_API_URL=OPENFGA_BASE_URL,
        OPENFGA_STORE_ID=store_id,
        OPENFGA_AUTHORIZATION_MODEL_ID=model_id,
    )


@pytest.fixture(scope="module")
def live_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject=f"live-test-{uuid.uuid4().hex[:8]}",
        issuer="test",  # NOT "local" — this is what actually keeps OpenFGA in play.
        audience="mism-api",
        scopes=set(),
    )


@pytest.fixture(scope="module")
def live_client(
    live_settings: Settings, live_principal: AuthenticatedPrincipal
) -> Generator[TestClient, None, None]:
    app = create_app(settings=live_settings)
    override_principal(app, live_principal)
    with TestClient(app) as client:
        yield client


@pytest.fixture()
async def raw_openfga_client(live_settings: Settings) -> AsyncGenerator[OpenFGAClient, None]:
    """A second, independent client for asserting on tuples — proves the API
    call actually wrote to OpenFGA, not just that it returned 201.

    Function-scoped and async (not module-scoped with asyncio.run() in
    teardown): its httpx.AsyncClient binds to whichever event loop is
    running when first used, so setup/use/teardown all need to share the
    one loop pytest-asyncio manages per test — see the comment on
    test_create_model_writes_real_tuples_after_role_granted.
    """
    client = OpenFGAClient(
        base_url=live_settings.openfga_api_url,
        store_id=live_settings.openfga_store_id,
        authorization_model_id=live_settings.openfga_authorization_model_id,
    )
    yield client
    await client.close()


def test_create_model_denied_without_uploader_role(live_client: TestClient) -> None:
    response = live_client.post(
        "/api/v1/models",
        json={
            "name": unique_name("live-model-denied"),
            "location_uri": "irods:///models/live",
            "execution_type": "docker",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_authorized"


async def test_create_model_writes_real_tuples_after_role_granted(
    live_client: TestClient,
    live_principal: AuthenticatedPrincipal,
    raw_openfga_client: OpenFGAClient,
) -> None:
    # async def, not asyncio.run() per call: raw_openfga_client's
    # httpx.AsyncClient binds its connection pool to whichever event loop is
    # running when it's first used. Multiple separate asyncio.run() calls
    # each spin up and tear down their own loop, so a second call orphans
    # the pool from the first ("RuntimeError: Event loop is closed"). A
    # single async test keeps every await on the one loop pytest-asyncio
    # manages for this test. live_client.post() (sync TestClient) is still
    # fine to call directly inside — it manages its own concurrency and
    # doesn't need the caller's loop.
    user = f"user:{live_principal.subject}"

    await raw_openfga_client.write_tuple(user=user, relation="uploader", object_="platform:main")

    response = live_client.post(
        "/api/v1/models",
        json={
            "name": unique_name("live-model-granted"),
            "location_uri": "irods:///models/live",
            "execution_type": "docker",
        },
    )
    assert response.status_code == 201
    model_id = response.json()["id"]

    owner_can_execute = await raw_openfga_client.check(
        user=user, relation="can_execute", object_=f"model:{model_id}"
    )
    assert owner_can_execute is True

    stranger_can_execute = await raw_openfga_client.check(
        user="user:someone-else", relation="can_execute", object_=f"model:{model_id}"
    )
    assert stranger_can_execute is False

    await raw_openfga_client.write_tuple(
        user="user:carol", relation="executor", object_="platform:main"
    )
    carol_can_execute = await raw_openfga_client.check(
        user="user:carol", relation="can_execute", object_=f"model:{model_id}"
    )
    assert carol_can_execute is True
