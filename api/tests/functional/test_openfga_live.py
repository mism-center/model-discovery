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
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from mism_registry import ResourceRegistrationStatus, set_registration_status
from mism_registry.backends.postgres import PostgresRegistry
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.clients.execution_client import ExecutionClient
from mismapi.clients.openfga_client import OpenFGAClient
from mismapi.core.deps import _get_execution_client
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


# ── Helpers for the role/relation-gate tests below ──────────────────
#
# Unlike `live_client`/`live_principal` above (module-scoped, shared by the
# two pre-existing tests, which rely on running in order: denied *before*
# the uploader role is granted), each test below needs a role check to
# start from a clean slate. Re-granting a tuple OpenFGA already has raises
# an error (Write is not an idempotent upsert), so reusing the shared
# module-scoped principal across tests would mean either fighting over
# grant order or re-granting duplicate tuples. Simplest and most robust:
# every test below mints its own fresh principal/client pair.


def _fresh_principal(prefix: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject=f"{prefix}-{uuid.uuid4().hex[:8]}",
        issuer="test",  # NOT "local" — keeps OpenFGA in play, see live_principal above.
        audience="mism-api",
        scopes=set(),
    )


@contextmanager
def _client_for(
    live_settings: Settings, principal: AuthenticatedPrincipal
) -> Generator[tuple[TestClient, AsyncMock], None, None]:
    """A fresh app + TestClient bound to `principal`, with the execution
    client mocked out (only the two execute_run tests below ever call it;
    harmless for the rest). `with`-managed like `live_client` above, so the
    app's lifespan (startup/shutdown) actually runs.
    """
    app = create_app(settings=live_settings)
    override_principal(app, principal)
    exec_client = AsyncMock(spec=ExecutionClient)
    app.dependency_overrides[_get_execution_client] = lambda: exec_client
    with TestClient(app) as client:
        yield client, exec_client


@contextmanager
def _direct_registry(live_settings: Settings) -> Generator[PostgresRegistry, None, None]:
    """A throwaway Postgres session/registry for test-setup mutations that
    have no reachable path through model-discovery's REST API — see
    `_advance_registration`.
    """
    engine = create_engine(live_settings.database_url, future=True)
    session = sessionmaker(bind=engine, expire_on_commit=False, future=True)()
    try:
        yield PostgresRegistry(session)
        session.commit()
    finally:
        session.close()
        engine.dispose()


def _advance_registration(
    live_settings: Settings, model_id: str, *targets: ResourceRegistrationStatus
) -> None:
    """Step a resource's registration_status through `targets` in order,
    directly against Postgres, bypassing the app layer entirely.

    DRAFT -> ANNOTATING -> PENDING_REVIEW has no endpoint in this app: in
    production that transition is driven by the external
    biomodel-annotator, not model-discovery. This is pure test-fixture
    setup for tests below that need a model past DRAFT — never the thing
    under test (the role-gated review/image-review/execute endpoints are).
    """
    with _direct_registry(live_settings) as registry:
        for target in targets:
            set_registration_status(
                registry,
                resource_id=model_id,
                target=target,
                reviewed_by="test-setup" if target == ResourceRegistrationStatus.APPROVED else "",
            )


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


# ── upload_reviewer (MISM-291 Phase 3) ───────────────────────────────


async def test_review_metadata_package_denied_without_upload_reviewer_role(
    live_settings: Settings, raw_openfga_client: OpenFGAClient
) -> None:
    principal = _fresh_principal("review-denied")
    user = f"user:{principal.subject}"
    await raw_openfga_client.write_tuple(user=user, relation="uploader", object_="platform:main")

    with _client_for(live_settings, principal) as (client, _exec_client):
        create_resp = client.post(
            "/api/v1/models",
            json={
                "name": unique_name("live-model-review-denied"),
                "location_uri": "irods:///models/live",
                "execution_type": "docker",
            },
        )
        assert create_resp.status_code == 201
        model_id = create_resp.json()["id"]

        # No upload_reviewer grant — denial happens before the (still-DRAFT)
        # model's state is even considered.
        response = client.post(f"/api/v1/models/{model_id}/review", json={"approve": True})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "not_authorized"


async def test_review_metadata_package_allowed_after_role_granted(
    live_settings: Settings, raw_openfga_client: OpenFGAClient
) -> None:
    principal = _fresh_principal("review-allowed")
    user = f"user:{principal.subject}"
    await raw_openfga_client.write_tuple(user=user, relation="uploader", object_="platform:main")

    with _client_for(live_settings, principal) as (client, _exec_client):
        create_resp = client.post(
            "/api/v1/models",
            json={
                "name": unique_name("live-model-review-allowed"),
                "location_uri": "irods:///models/live",
                "execution_type": "docker",
            },
        )
        assert create_resp.status_code == 201
        model_id = create_resp.json()["id"]

        _advance_registration(
            live_settings,
            model_id,
            ResourceRegistrationStatus.ANNOTATING,
            ResourceRegistrationStatus.PENDING_REVIEW,
        )
        await raw_openfga_client.write_tuple(
            user=user, relation="upload_reviewer", object_="platform:main"
        )

        response = client.post(f"/api/v1/models/{model_id}/review", json={"approve": True})
        assert response.status_code == 200
        assert response.json()["registration_status"] == "approved"


# ── image_checker (MISM-291 Phase 4) ─────────────────────────────────


async def test_image_review_denied_without_image_checker_role(
    live_settings: Settings, raw_openfga_client: OpenFGAClient
) -> None:
    principal = _fresh_principal("image-review-denied")
    user = f"user:{principal.subject}"
    await raw_openfga_client.write_tuple(user=user, relation="uploader", object_="platform:main")

    with _client_for(live_settings, principal) as (client, _exec_client):
        create_resp = client.post(
            "/api/v1/models",
            json={
                "name": unique_name("live-model-image-review-denied"),
                "location_uri": "irods:///models/live",
                "execution_type": "docker",
            },
        )
        assert create_resp.status_code == 201
        model_id = create_resp.json()["id"]

        # No image_checker grant — denial happens before any image-review
        # state is even considered.
        response = client.post(f"/api/v1/models/{model_id}/image-review", json={"approve": True})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "not_authorized"


async def test_image_review_allowed_after_role_granted(
    live_settings: Settings, raw_openfga_client: OpenFGAClient
) -> None:
    """Full chain: upload -> metadata review/approve -> submit image ->
    image review/approve — the same workflow steps (a) through (k)."""
    principal = _fresh_principal("image-review-allowed")
    user = f"user:{principal.subject}"
    await raw_openfga_client.write_tuple(user=user, relation="uploader", object_="platform:main")

    with _client_for(live_settings, principal) as (client, _exec_client):
        create_resp = client.post(
            "/api/v1/models",
            json={
                "name": unique_name("live-model-image-review-allowed"),
                "location_uri": "irods:///models/live",
                "execution_type": "docker",
            },
        )
        assert create_resp.status_code == 201
        model_id = create_resp.json()["id"]

        _advance_registration(
            live_settings,
            model_id,
            ResourceRegistrationStatus.ANNOTATING,
            ResourceRegistrationStatus.PENDING_REVIEW,
        )
        await raw_openfga_client.write_tuple(
            user=user, relation="upload_reviewer", object_="platform:main"
        )
        review_resp = client.post(f"/api/v1/models/{model_id}/review", json={"approve": True})
        assert review_resp.status_code == 200
        assert review_resp.json()["registration_status"] == "approved"

        # Submitting the image is ownership-gated, not role-gated (steps h/l).
        submit_resp = client.post(
            f"/api/v1/models/{model_id}/image",
            json={"kind": "docker", "file": "Dockerfile", "image_name": "example:latest"},
        )
        assert submit_resp.status_code == 200
        assert submit_resp.json()["image_review_status"] == "pending_image_check"

        await raw_openfga_client.write_tuple(
            user=user, relation="image_checker", object_="platform:main"
        )
        response = client.post(f"/api/v1/models/{model_id}/image-review", json={"approve": True})
        assert response.status_code == 200
        assert response.json()["image_review_status"] == "image_approved"


# ── can_execute (MISM-291 Phase 5) ───────────────────────────────────


async def test_execute_run_denied_without_can_execute(
    live_settings: Settings, raw_openfga_client: OpenFGAClient
) -> None:
    owner = _fresh_principal("execute-owner")
    owner_user = f"user:{owner.subject}"
    await raw_openfga_client.write_tuple(
        user=owner_user, relation="uploader", object_="platform:main"
    )

    with _client_for(live_settings, owner) as (owner_client, _owner_exec_client):
        create_resp = owner_client.post(
            "/api/v1/models",
            json={
                "name": unique_name("live-model-execute-denied"),
                "location_uri": "irods:///models/live",
                "execution_type": "docker",
            },
        )
        assert create_resp.status_code == 201
        model_id = create_resp.json()["id"]
        _advance_registration(
            live_settings,
            model_id,
            ResourceRegistrationStatus.ANNOTATING,
            ResourceRegistrationStatus.PENDING_REVIEW,
            ResourceRegistrationStatus.APPROVED,
        )

    # A stranger: no ownership, no executor grant.
    stranger = _fresh_principal("execute-stranger")
    with _client_for(live_settings, stranger) as (stranger_client, stranger_exec_client):
        response = stranger_client.post(
            f"/api/v1/models/{model_id}/runs",
            json={"input_resource_ids": []},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "not_authorized"
        stranger_exec_client.launch_batch.assert_not_awaited()
        stranger_exec_client.launch_interactive.assert_not_awaited()


async def test_execute_run_allowed_for_platform_executor(
    live_settings: Settings, raw_openfga_client: OpenFGAClient
) -> None:
    owner = _fresh_principal("execute-owner2")
    owner_user = f"user:{owner.subject}"
    await raw_openfga_client.write_tuple(
        user=owner_user, relation="uploader", object_="platform:main"
    )

    with _client_for(live_settings, owner) as (owner_client, _owner_exec_client):
        create_resp = owner_client.post(
            "/api/v1/models",
            json={
                "name": unique_name("live-model-execute-allowed"),
                "location_uri": "irods:///models/live",
                "execution_type": "docker",
            },
        )
        assert create_resp.status_code == 201
        model_id = create_resp.json()["id"]
        _advance_registration(
            live_settings,
            model_id,
            ResourceRegistrationStatus.ANNOTATING,
            ResourceRegistrationStatus.PENDING_REVIEW,
            ResourceRegistrationStatus.APPROVED,
        )

    # Holds platform:main#executor, but neither owns nor uploaded the model.
    executor = _fresh_principal("execute-executor")
    executor_user = f"user:{executor.subject}"
    await raw_openfga_client.write_tuple(
        user=executor_user, relation="executor", object_="platform:main"
    )

    with _client_for(live_settings, executor) as (executor_client, exec_client):
        exec_client.launch_batch.return_value = {"launched": True}
        response = executor_client.post(
            f"/api/v1/models/{model_id}/runs",
            json={"input_resource_ids": []},
        )
        assert response.status_code == 201
        assert response.json()["execution"] == {"launched": True}
        exec_client.launch_batch.assert_awaited_once()
